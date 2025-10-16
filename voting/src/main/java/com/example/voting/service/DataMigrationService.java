package com.example.voting.service;

import com.example.voting.model.Origami;
import com.example.voting.repository.OrigamiRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Service for migrating and synchronizing data from the Catalogue service.
 * 
 * This service handles the initial data migration and ongoing synchronization
 * of origami products from the catalogue service to the voting database.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DataMigrationService {

    private final OrigamiRepository origamiRepository;
    private final JdbcTemplate jdbcTemplate;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    @Value("${catalogue.service.url:http://localhost:5000}")
    private String catalogueServiceUrl;

    @Value("${migration.batch.size:50}")
    private int batchSize;

    /**
     * DTO for catalogue service product data.
     */
    public static class CatalogueProduct {
        public String id;
        public String name;
        public String description;
        public String image_url;
        public String imageUrl; // Alternative field name
        public Boolean active;
        public Map<String, Object> attributes;

        public String getImageUrl() {
            return image_url != null ? image_url : imageUrl;
        }
    }

    /**
     * DTO for migration statistics.
     */
    public static class MigrationStats {
        public int totalProcessed;
        public int created;
        public int updated;
        public int deactivated;
        public int errors;
        public long durationMs;
        public String status;
        public String errorMessage;
    }

    /**
     * Perform initial data migration from catalogue service.
     * 
     * @return Migration statistics
     */
    @Transactional
    public MigrationStats performInitialMigration() {
        log.info("Starting initial data migration from catalogue service");
        long startTime = System.currentTimeMillis();
        
        MigrationStats stats = new MigrationStats();
        stats.status = "SUCCESS";
        
        try {
            // Fetch products from catalogue service
            List<CatalogueProduct> catalogueProducts = fetchProductsFromCatalogue();
            stats.totalProcessed = catalogueProducts.size();
            
            if (catalogueProducts.isEmpty()) {
                log.warn("No products found in catalogue service");
                return stats;
            }
            
            // Process products in batches
            List<String> activeOrigamiIds = new ArrayList<>();
            
            for (int i = 0; i < catalogueProducts.size(); i += batchSize) {
                int endIndex = Math.min(i + batchSize, catalogueProducts.size());
                List<CatalogueProduct> batch = catalogueProducts.subList(i, endIndex);
                
                MigrationStats batchStats = processBatch(batch);
                stats.created += batchStats.created;
                stats.updated += batchStats.updated;
                stats.errors += batchStats.errors;
                
                // Collect active origami IDs
                batch.stream()
                    .filter(p -> p.active == null || p.active)
                    .map(p -> p.id)
                    .forEach(activeOrigamiIds::add);
            }
            
            // Deactivate origami that no longer exist in catalogue
            stats.deactivated = deactivateMissingOrigami(activeOrigamiIds);
            
            stats.durationMs = System.currentTimeMillis() - startTime;
            
            // Log migration event
            logMigrationEvent("INITIAL_MIGRATION", stats);
            
            log.info("Initial migration completed: {} processed, {} created, {} updated, {} deactivated, {} errors",
                    stats.totalProcessed, stats.created, stats.updated, stats.deactivated, stats.errors);
            
        } catch (Exception e) {
            stats.status = "ERROR";
            stats.errorMessage = e.getMessage();
            stats.durationMs = System.currentTimeMillis() - startTime;
            
            log.error("Initial migration failed", e);
            logMigrationEvent("INITIAL_MIGRATION", stats);
        }
        
        return stats;
    }

    /**
     * Perform incremental synchronization with catalogue service.
     * 
     * @return Synchronization statistics
     */
    @Transactional
    public MigrationStats performIncrementalSync() {
        log.info("Starting incremental synchronization with catalogue service");
        long startTime = System.currentTimeMillis();
        
        MigrationStats stats = new MigrationStats();
        stats.status = "SUCCESS";
        
        try {
            // Fetch products from catalogue service
            List<CatalogueProduct> catalogueProducts = fetchProductsFromCatalogue();
            stats.totalProcessed = catalogueProducts.size();
            
            // Get existing origami from database
            Map<String, Origami> existingOrigami = origamiRepository.findAll()
                    .stream()
                    .collect(Collectors.toMap(Origami::getOrigamiId, o -> o));
            
            List<String> activeOrigamiIds = new ArrayList<>();
            
            for (CatalogueProduct product : catalogueProducts) {
                try {
                    if (product.active == null || product.active) {
                        activeOrigamiIds.add(product.id);
                        
                        Origami existing = existingOrigami.get(product.id);
                        if (existing == null) {
                            // Create new origami
                            createOrigamiFromProduct(product);
                            stats.created++;
                        } else if (needsUpdate(existing, product)) {
                            // Update existing origami
                            updateOrigamiFromProduct(existing, product);
                            stats.updated++;
                        }
                    }
                } catch (Exception e) {
                    log.error("Error processing product {}: {}", product.id, e.getMessage());
                    stats.errors++;
                }
            }
            
            // Deactivate origami that no longer exist in catalogue
            stats.deactivated = deactivateMissingOrigami(activeOrigamiIds);
            
            stats.durationMs = System.currentTimeMillis() - startTime;
            
            // Log sync event
            logMigrationEvent("INCREMENTAL_SYNC", stats);
            
            log.info("Incremental sync completed: {} processed, {} created, {} updated, {} deactivated, {} errors",
                    stats.totalProcessed, stats.created, stats.updated, stats.deactivated, stats.errors);
            
        } catch (Exception e) {
            stats.status = "ERROR";
            stats.errorMessage = e.getMessage();
            stats.durationMs = System.currentTimeMillis() - startTime;
            
            log.error("Incremental sync failed", e);
            logMigrationEvent("INCREMENTAL_SYNC", stats);
        }
        
        return stats;
    }

    /**
     * Fetch products from catalogue service API.
     */
    private List<CatalogueProduct> fetchProductsFromCatalogue() {
        try {
            String url = catalogueServiceUrl + "/api/products";
            log.debug("Fetching products from: {}", url);
            
            String response = restTemplate.getForObject(url, String.class);
            
            if (response == null || response.trim().isEmpty()) {
                log.warn("Empty response from catalogue service");
                return Collections.emptyList();
            }
            
            // Parse JSON response
            JsonNode jsonNode = objectMapper.readTree(response);
            
            if (jsonNode.isArray()) {
                return objectMapper.convertValue(jsonNode, new TypeReference<List<CatalogueProduct>>() {});
            } else {
                log.warn("Unexpected response format from catalogue service");
                return Collections.emptyList();
            }
            
        } catch (Exception e) {
            log.error("Failed to fetch products from catalogue service", e);
            throw new RuntimeException("Failed to fetch products from catalogue service", e);
        }
    }

    /**
     * Process a batch of catalogue products.
     */
    private MigrationStats processBatch(List<CatalogueProduct> products) {
        MigrationStats stats = new MigrationStats();
        
        for (CatalogueProduct product : products) {
            try {
                if (product.active == null || product.active) {
                    Optional<Origami> existing = origamiRepository.findByOrigamiIdAndActiveTrue(product.id);
                    
                    if (existing.isEmpty()) {
                        createOrigamiFromProduct(product);
                        stats.created++;
                    } else if (needsUpdate(existing.get(), product)) {
                        updateOrigamiFromProduct(existing.get(), product);
                        stats.updated++;
                    }
                }
            } catch (Exception e) {
                log.error("Error processing product {}: {}", product.id, e.getMessage());
                stats.errors++;
            }
        }
        
        return stats;
    }

    /**
     * Create new Origami entity from catalogue product.
     */
    private void createOrigamiFromProduct(CatalogueProduct product) {
        Origami origami = Origami.builder()
                .origamiId(product.id)
                .name(product.name)
                .description(product.description)
                .imageUrl(product.getImageUrl())
                .voteCount(0)
                .active(true)
                .build();
        
        origamiRepository.save(origami);
        log.debug("Created new origami: {} (ID: {})", origami.getName(), origami.getOrigamiId());
    }

    /**
     * Update existing Origami entity from catalogue product.
     */
    private void updateOrigamiFromProduct(Origami existing, CatalogueProduct product) {
        existing.setName(product.name);
        existing.setDescription(product.description);
        existing.setImageUrl(product.getImageUrl());
        
        origamiRepository.save(existing);
        log.debug("Updated origami: {} (ID: {})", existing.getName(), existing.getOrigamiId());
    }

    /**
     * Check if origami needs update based on catalogue product data.
     */
    private boolean needsUpdate(Origami existing, CatalogueProduct product) {
        return !Objects.equals(existing.getName(), product.name) ||
               !Objects.equals(existing.getDescription(), product.description) ||
               !Objects.equals(existing.getImageUrl(), product.getImageUrl());
    }

    /**
     * Deactivate origami that no longer exist in catalogue.
     */
    private int deactivateMissingOrigami(List<String> activeOrigamiIds) {
        if (activeOrigamiIds.isEmpty()) {
            return 0;
        }
        
        try {
            String sql = "SELECT deactivate_missing_origami(?)";
            String[] idsArray = activeOrigamiIds.toArray(new String[0]);
            
            Integer deactivatedCount = jdbcTemplate.queryForObject(sql, Integer.class, (Object) idsArray);
            
            if (deactivatedCount != null && deactivatedCount > 0) {
                log.info("Deactivated {} origami that no longer exist in catalogue", deactivatedCount);
            }
            
            return deactivatedCount != null ? deactivatedCount : 0;
            
        } catch (Exception e) {
            log.error("Failed to deactivate missing origami", e);
            return 0;
        }
    }

    /**
     * Log migration event to database.
     */
    private void logMigrationEvent(String syncType, MigrationStats stats) {
        try {
            String sql = "SELECT log_sync_event(?, ?, ?, ?, ?, ?, ?, ?)";
            
            jdbcTemplate.queryForObject(sql, Long.class,
                    syncType,
                    stats.totalProcessed,
                    stats.updated,
                    stats.created,
                    stats.deactivated,
                    stats.status,
                    stats.errorMessage,
                    (int) stats.durationMs
            );
            
        } catch (Exception e) {
            log.error("Failed to log migration event", e);
        }
    }

    /**
     * Get synchronization statistics from database.
     */
    public Map<String, Object> getSyncStatistics() {
        try {
            String sql = "SELECT * FROM get_sync_statistics()";
            
            return jdbcTemplate.queryForMap(sql);
            
        } catch (Exception e) {
            log.error("Failed to get sync statistics", e);
            return Collections.emptyMap();
        }
    }

    /**
     * Get recent synchronization history.
     */
    public List<Map<String, Object>> getSyncHistory(int limit) {
        try {
            String sql = "SELECT * FROM sync_history ORDER BY created_at DESC LIMIT ?";
            
            return jdbcTemplate.queryForList(sql, limit);
            
        } catch (Exception e) {
            log.error("Failed to get sync history", e);
            return Collections.emptyList();
        }
    }
}