package com.example.voting.service;

import com.example.voting.model.Origami;
import com.example.voting.repository.OrigamiRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Enhanced service layer for Origami repository operations.
 * 
 * Provides business logic, error handling, and data synchronization
 * capabilities for the voting service with proper transaction management.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OrigamiRepositoryService {

    private final OrigamiRepository origamiRepository;

    /**
     * Retrieve all active origami items with pagination.
     */
    @Transactional(readOnly = true)
    public Page<Origami> getAllActiveOrigami(int page, int size, String sortBy, String sortDirection) {
        try {
            Sort.Direction direction = Sort.Direction.fromString(sortDirection);
            Pageable pageable = PageRequest.of(page, size, Sort.by(direction, sortBy));
            return origamiRepository.findByActiveTrue(pageable);
        } catch (Exception e) {
            log.error("Failed to retrieve active origami items: {}", e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to retrieve active origami items", e);
        }
    }

    /**
     * Retrieve all active origami items as a list.
     */
    @Transactional(readOnly = true)
    public List<Origami> getAllActiveOrigamiList() {
        try {
            return origamiRepository.findByActiveTrue();
        } catch (DataAccessException e) {
            log.error("Failed to retrieve active origami list: {}", e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to retrieve active origami list", e);
        }
    }

    /**
     * Find origami by external ID.
     */
    @Transactional(readOnly = true)
    public Optional<Origami> findByOrigamiId(String origamiId) {
        try {
            validateOrigamiId(origamiId);
            return origamiRepository.findByOrigamiIdAndActiveTrue(origamiId);
        } catch (DataAccessException e) {
            log.error("Failed to find origami by ID {}: {}", origamiId, e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to find origami by ID: " + origamiId, e);
        }
    }

    /**
     * Create or update origami from catalogue service data.
     * This method handles data synchronization from the catalogue service.
     */
    @Transactional
    public Origami createOrUpdateOrigami(String origamiId, String name, String description, String imageUrl) {
        try {
            validateOrigamiData(origamiId, name);
            
            Optional<Origami> existingOrigami = origamiRepository.findByOrigamiId(origamiId);
            
            if (existingOrigami.isPresent()) {
                // Update existing origami
                Origami origami = existingOrigami.get();
                origami.setName(name);
                origami.setDescription(description);
                origami.setImageUrl(imageUrl);
                origami.setActive(true); // Reactivate if it was soft deleted
                
                Origami savedOrigami = origamiRepository.save(origami);
                log.info("Updated origami: {} with ID: {}", name, origamiId);
                return savedOrigami;
            } else {
                // Create new origami
                Origami newOrigami = Origami.builder()
                    .origamiId(origamiId)
                    .name(name)
                    .description(description)
                    .imageUrl(imageUrl)
                    .voteCount(0)
                    .active(true)
                    .build();
                
                Origami savedOrigami = origamiRepository.save(newOrigami);
                log.info("Created new origami: {} with ID: {}", name, origamiId);
                return savedOrigami;
            }
        } catch (DataAccessException e) {
            log.error("Failed to create or update origami {}: {}", origamiId, e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to create or update origami: " + origamiId, e);
        }
    }

    /**
     * Atomically increment vote count with retry logic for optimistic locking.
     */
    @Retryable(value = {OptimisticLockingFailureException.class}, maxAttempts = 3, backoff = @Backoff(delay = 100))
    @Transactional
    public boolean incrementVoteCount(String origamiId) {
        try {
            validateOrigamiId(origamiId);
            
            int updatedRows = origamiRepository.incrementVoteCountByOrigamiId(origamiId);
            
            if (updatedRows > 0) {
                log.info("Successfully incremented vote count for origami: {}", origamiId);
                return true;
            } else {
                log.warn("No active origami found with ID: {} for vote increment", origamiId);
                return false;
            }
        } catch (OptimisticLockingFailureException e) {
            log.warn("Optimistic locking failure when incrementing vote for {}, retrying...", origamiId);
            throw e; // Will trigger retry
        } catch (DataAccessException e) {
            log.error("Failed to increment vote count for origami {}: {}", origamiId, e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to increment vote count for origami: " + origamiId, e);
        }
    }

    /**
     * Get top origami by vote count.
     */
    @Transactional(readOnly = true)
    public List<Origami> getTopOrigamiByVotes(int limit) {
        try {
            Pageable pageable = PageRequest.of(0, limit);
            return origamiRepository.findTopByVoteCount(pageable);
        } catch (DataAccessException e) {
            log.error("Failed to retrieve top origami by votes: {}", e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to retrieve top origami by votes", e);
        }
    }

    /**
     * Soft delete origami by external ID.
     */
    @Transactional
    public boolean softDeleteOrigami(String origamiId) {
        try {
            validateOrigamiId(origamiId);
            
            int updatedRows = origamiRepository.softDeleteByOrigamiId(origamiId);
            
            if (updatedRows > 0) {
                log.info("Successfully soft deleted origami: {}", origamiId);
                return true;
            } else {
                log.warn("No origami found with ID: {} for soft deletion", origamiId);
                return false;
            }
        } catch (DataAccessException e) {
            log.error("Failed to soft delete origami {}: {}", origamiId, e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to soft delete origami: " + origamiId, e);
        }
    }

    /**
     * Search origami by name pattern.
     */
    @Transactional(readOnly = true)
    public List<Origami> searchOrigamiByName(String namePattern) {
        try {
            if (namePattern == null || namePattern.trim().isEmpty()) {
                return List.of();
            }
            
            return origamiRepository.findByNameContainingIgnoreCase(namePattern.trim());
        } catch (DataAccessException e) {
            log.error("Failed to search origami by name pattern {}: {}", namePattern, e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to search origami by name pattern: " + namePattern, e);
        }
    }

    /**
     * Get vote count statistics.
     */
    @Transactional(readOnly = true)
    public VoteStatistics getVoteStatistics() {
        try {
            Object[] stats = origamiRepository.getVoteCountStatistics();
            
            if (stats != null && stats.length >= 4) {
                return VoteStatistics.builder()
                    .minVotes(stats[0] != null ? ((Number) stats[0]).intValue() : 0)
                    .maxVotes(stats[1] != null ? ((Number) stats[1]).intValue() : 0)
                    .averageVotes(stats[2] != null ? ((Number) stats[2]).doubleValue() : 0.0)
                    .totalOrigami(stats[3] != null ? ((Number) stats[3]).longValue() : 0L)
                    .build();
            }
            
            return VoteStatistics.builder().build();
        } catch (DataAccessException e) {
            log.error("Failed to retrieve vote statistics: {}", e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to retrieve vote statistics", e);
        }
    }

    /**
     * Find origami items that need synchronization with catalogue service.
     */
    @Transactional(readOnly = true)
    public List<Origami> findOrigamiNeedingSync(int hoursThreshold) {
        try {
            LocalDateTime threshold = LocalDateTime.now().minusHours(hoursThreshold);
            return origamiRepository.findOrigamiNeedingSync(threshold);
        } catch (DataAccessException e) {
            log.error("Failed to find origami needing sync: {}", e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to find origami needing sync", e);
        }
    }

    /**
     * Bulk synchronize origami data from catalogue service.
     */
    @Transactional
    public int bulkSynchronizeOrigami(List<OrigamiSyncData> syncDataList) {
        int syncedCount = 0;
        
        for (OrigamiSyncData syncData : syncDataList) {
            try {
                createOrUpdateOrigami(
                    syncData.getOrigamiId(),
                    syncData.getName(),
                    syncData.getDescription(),
                    syncData.getImageUrl()
                );
                syncedCount++;
            } catch (Exception e) {
                log.error("Failed to sync origami {}: {}", syncData.getOrigamiId(), e.getMessage(), e);
                // Continue with other items instead of failing the entire batch
            }
        }
        
        log.info("Successfully synchronized {} out of {} origami items", syncedCount, syncDataList.size());
        return syncedCount;
    }

    /**
     * Check if origami exists by external ID.
     */
    @Transactional(readOnly = true)
    public boolean existsByOrigamiId(String origamiId) {
        try {
            validateOrigamiId(origamiId);
            return origamiRepository.existsByOrigamiId(origamiId);
        } catch (DataAccessException e) {
            log.error("Failed to check existence of origami {}: {}", origamiId, e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to check existence of origami: " + origamiId, e);
        }
    }

    /**
     * Get count of origami by external ID (should be 0 or 1).
     */
    @Transactional(readOnly = true)
    public int countByOrigamiId(String origamiId) {
        try {
            validateOrigamiId(origamiId);
            return origamiRepository.countByOrigamiId(origamiId);
        } catch (DataAccessException e) {
            log.error("Failed to count origami by ID {}: {}", origamiId, e.getMessage(), e);
            throw new OrigamiRepositoryException("Failed to count origami by ID: " + origamiId, e);
        }
    }

    // Validation methods
    private void validateOrigamiId(String origamiId) {
        if (origamiId == null || origamiId.trim().isEmpty()) {
            throw new IllegalArgumentException("Origami ID cannot be null or empty");
        }
        if (origamiId.length() > 50) {
            throw new IllegalArgumentException("Origami ID cannot exceed 50 characters");
        }
    }

    private void validateOrigamiData(String origamiId, String name) {
        validateOrigamiId(origamiId);
        
        if (name == null || name.trim().isEmpty()) {
            throw new IllegalArgumentException("Origami name cannot be null or empty");
        }
        if (name.length() > 255) {
            throw new IllegalArgumentException("Origami name cannot exceed 255 characters");
        }
    }

    // Data transfer objects
    public static class OrigamiSyncData {
        private String origamiId;
        private String name;
        private String description;
        private String imageUrl;

        // Constructors
        public OrigamiSyncData() {}

        public OrigamiSyncData(String origamiId, String name, String description, String imageUrl) {
            this.origamiId = origamiId;
            this.name = name;
            this.description = description;
            this.imageUrl = imageUrl;
        }

        // Getters and setters
        public String getOrigamiId() { return origamiId; }
        public void setOrigamiId(String origamiId) { this.origamiId = origamiId; }
        
        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
        
        public String getDescription() { return description; }
        public void setDescription(String description) { this.description = description; }
        
        public String getImageUrl() { return imageUrl; }
        public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl; }
    }

    @lombok.Builder
    @lombok.Data
    public static class VoteStatistics {
        private int minVotes;
        private int maxVotes;
        private double averageVotes;
        private long totalOrigami;
    }

    // Custom exception for repository operations
    public static class OrigamiRepositoryException extends RuntimeException {
        public OrigamiRepositoryException(String message) {
            super(message);
        }

        public OrigamiRepositoryException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}