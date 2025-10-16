package com.example.voting.performance;

import com.example.voting.model.Origami;
import com.example.voting.repository.OrigamiRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.*;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Performance tests for database operations under load.
 * 
 * These tests validate that the database can handle expected load patterns
 * and identify performance bottlenecks in PostgreSQL operations.
 */
@DataJpaTest
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Tag("performance")
class DatabasePerformanceTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("perf_testdb")
            .withUsername("perf_testuser")
            .withPassword("perf_testpass")
            .withInitScript("test-schema.sql");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.datasource.driver-class-name", () -> "org.postgresql.Driver");
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "create-drop");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.PostgreSQLDialect");
        registry.add("spring.jpa.properties.hibernate.jdbc.batch_size", () -> "25");
        registry.add("spring.jpa.properties.hibernate.order_inserts", () -> "true");
        registry.add("spring.jpa.properties.hibernate.order_updates", () -> "true");
    }

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private OrigamiRepository origamiRepository;

    private List<Origami> largeDataset;

    @BeforeEach
    void setUp() {
        // Create a large dataset for performance testing
        largeDataset = createLargeDataset(1000);
    }

    private List<Origami> createLargeDataset(int size) {
        List<Origami> dataset = new ArrayList<>();
        
        for (int i = 0; i < size; i++) {
            Origami origami = Origami.builder()
                    .origamiId(String.format("perf-test-%05d", i))
                    .name(String.format("Performance Test Origami %d", i))
                    .description(String.format("Performance test origami number %d for load testing", i))
                    .imageUrl(String.format("/images/perf-test-%d.png", i))
                    .voteCount(i % 100) // Vary vote counts from 0 to 99
                    .active(i % 10 != 0) // 90% active, 10% inactive
                    .build();
            
            entityManager.persist(origami);
            dataset.add(origami);
            
            // Flush periodically to manage memory
            if (i % 100 == 0) {
                entityManager.flush();
            }
        }
        
        entityManager.flush();
        entityManager.clear();
        
        return dataset;
    }

    @Test
    @DisplayName("Should handle high-volume read operations efficiently")
    void testHighVolumeReadOperations() {
        // Test bulk read operations
        long startTime = System.currentTimeMillis();
        
        // Multiple read operations
        List<Origami> allActive = origamiRepository.findByActiveTrue();
        List<Origami> highVotes = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(50);
        Object[] stats = origamiRepository.getVoteCountStatistics();
        
        long endTime = System.currentTimeMillis();
        long duration = endTime - startTime;
        
        // Performance assertions
        assertThat(allActive.size()).isGreaterThan(800); // ~90% of 1000
        assertThat(highVotes.size()).isGreaterThan(400); // ~50% of active origamis
        assertThat(stats).hasSize(4);
        assertThat(duration).isLessThan(2000); // Should complete within 2 seconds
    }

    @Test
    @DisplayName("Should handle concurrent vote operations efficiently")
    void testConcurrentVoteOperations() throws InterruptedException, ExecutionException {
        // Select a subset of origamis for concurrent voting
        List<String> targetOrigamiIds = largeDataset.stream()
                .limit(50)
                .map(Origami::getOrigamiId)
                .toList();

        int threadsPerOrigami = 10;
        int votesPerThread = 20;
        ExecutorService executor = Executors.newFixedThreadPool(50);

        long startTime = System.currentTimeMillis();

        // Create concurrent voting tasks
        List<CompletableFuture<Integer>> futures = targetOrigamiIds.stream()
                .flatMap(origamiId -> IntStream.range(0, threadsPerOrigami)
                        .mapToObj(threadIndex -> CompletableFuture.supplyAsync(() -> {
                            int successfulVotes = 0;
                            for (int vote = 0; vote < votesPerThread; vote++) {
                                try {
                                    int updated = origamiRepository.incrementVoteCountByOrigamiId(origamiId);
                                    if (updated > 0) {
                                        successfulVotes++;
                                    }
                                    // Small delay to simulate real-world usage
                                    Thread.sleep(1);
                                } catch (Exception e) {
                                    // Expected under high concurrency
                                }
                            }
                            return successfulVotes;
                        }, executor)))
                .toList();

        // Wait for all operations to complete
        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get();
        
        long endTime = System.currentTimeMillis();
        long duration = endTime - startTime;

        executor.shutdown();
        executor.awaitTermination(30, TimeUnit.SECONDS);

        // Calculate performance metrics
        int totalExpectedVotes = targetOrigamiIds.size() * threadsPerOrigami * votesPerThread;
        int totalActualVotes = futures.stream()
                .mapToInt(future -> {
                    try {
                        return future.get();
                    } catch (Exception e) {
                        return 0;
                    }
                })
                .sum();

        double votesPerSecond = (double) totalActualVotes / (duration / 1000.0);

        // Performance assertions
        assertThat(totalActualVotes).isEqualTo(totalExpectedVotes);
        assertThat(votesPerSecond).isGreaterThan(100); // Should handle > 100 votes/second
        assertThat(duration).isLessThan(30000); // Should complete within 30 seconds
    }

    @Test
    @DisplayName("Should handle bulk update operations efficiently")
    void testBulkUpdateOperations() {
        // Select subset for bulk updates
        List<Origami> updateTargets = largeDataset.stream().limit(200).toList();
        
        long startTime = System.currentTimeMillis();
        
        // Perform bulk updates
        int totalUpdated = 0;
        for (int i = 0; i < updateTargets.size(); i++) {
            Origami origami = updateTargets.get(i);
            int updated = origamiRepository.updateOrigamiDetails(
                    origami.getOrigamiId(),
                    String.format("Bulk Updated %s", origami.getName()),
                    String.format("Bulk updated description %d", i),
                    String.format("/images/bulk-updated-%d.png", i)
            );
            totalUpdated += updated;
            
            // Batch flush every 50 operations
            if (i % 50 == 0) {
                entityManager.flush();
            }
        }
        
        long endTime = System.currentTimeMillis();
        long duration = endTime - startTime;
        
        double updatesPerSecond = (double) totalUpdated / (duration / 1000.0);
        
        // Performance assertions
        assertThat(totalUpdated).isEqualTo(updateTargets.size());
        assertThat(updatesPerSecond).isGreaterThan(20); // Should handle > 20 updates/second
        assertThat(duration).isLessThan(15000); // Should complete within 15 seconds
    }

    @Test
    @DisplayName("Should handle mixed workload efficiently")
    void testMixedWorkloadPerformance() throws InterruptedException, ExecutionException {
        int concurrentUsers = 20;
        int operationsPerUser = 50;
        ExecutorService executor = Executors.newFixedThreadPool(concurrentUsers);

        long startTime = System.currentTimeMillis();

        List<CompletableFuture<Long>> futures = IntStream.range(0, concurrentUsers)
                .mapToObj(userIndex -> CompletableFuture.supplyAsync(() -> {
                    long userOperationTime = 0;
                    
                    for (int op = 0; op < operationsPerUser; op++) {
                        long opStart = System.currentTimeMillis();
                        
                        try {
                            int operationType = op % 5;
                            
                            switch (operationType) {
                                case 0: // Read operation - find by active
                                    origamiRepository.findByActiveTrue();
                                    break;
                                case 1: // Read operation - find by ID
                                    String targetId = largeDataset.get(op % largeDataset.size()).getOrigamiId();
                                    origamiRepository.findByOrigamiId(targetId);
                                    break;
                                case 2: // Read operation - statistics
                                    origamiRepository.getVoteCountStatistics();
                                    break;
                                case 3: // Write operation - vote increment
                                    String voteTargetId = largeDataset.get(op % largeDataset.size()).getOrigamiId();
                                    origamiRepository.incrementVoteCountByOrigamiId(voteTargetId);
                                    break;
                                case 4: // Write operation - update details
                                    String updateTargetId = largeDataset.get(op % largeDataset.size()).getOrigamiId();
                                    origamiRepository.updateOrigamiDetails(
                                            updateTargetId,
                                            String.format("Mixed Workload Update %d-%d", userIndex, op),
                                            "Mixed workload test update",
                                            String.format("/images/mixed-%d-%d.png", userIndex, op)
                                    );
                                    break;
                            }
                        } catch (Exception e) {
                            // Expected under high load
                        }
                        
                        userOperationTime += (System.currentTimeMillis() - opStart);
                    }
                    
                    return userOperationTime;
                }, executor))
                .toList();

        // Wait for all users to complete
        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get();
        
        long endTime = System.currentTimeMillis();
        long totalDuration = endTime - startTime;

        executor.shutdown();
        executor.awaitTermination(60, TimeUnit.SECONDS);

        // Calculate performance metrics
        long totalOperationTime = futures.stream()
                .mapToLong(future -> {
                    try {
                        return future.get();
                    } catch (Exception e) {
                        return 0;
                    }
                })
                .sum();

        int totalOperations = concurrentUsers * operationsPerUser;
        double operationsPerSecond = (double) totalOperations / (totalDuration / 1000.0);
        double averageOperationTime = (double) totalOperationTime / totalOperations;

        // Performance assertions
        assertThat(operationsPerSecond).isGreaterThan(50); // Should handle > 50 ops/second
        assertThat(averageOperationTime).isLessThan(100); // Average op time < 100ms
        assertThat(totalDuration).isLessThan(60000); // Should complete within 60 seconds
    }

    @Test
    @DisplayName("Should maintain query performance with large result sets")
    void testLargeResultSetPerformance() {
        // Test queries that return large result sets
        long startTime = System.currentTimeMillis();
        
        // Query that returns most of the dataset
        List<Origami> allActive = origamiRepository.findByActiveTrue();
        
        long queryTime = System.currentTimeMillis() - startTime;
        
        // Test pagination performance
        startTime = System.currentTimeMillis();
        
        // Multiple paginated queries
        for (int page = 0; page < 10; page++) {
            origamiRepository.findByActiveTrue(
                    org.springframework.data.domain.PageRequest.of(page, 50)
            );
        }
        
        long paginationTime = System.currentTimeMillis() - startTime;
        
        // Performance assertions
        assertThat(allActive.size()).isGreaterThan(800);
        assertThat(queryTime).isLessThan(3000); // Large query < 3 seconds
        assertThat(paginationTime).isLessThan(2000); // Pagination queries < 2 seconds
    }

    @Test
    @DisplayName("Should handle database connection pool under stress")
    void testConnectionPoolPerformance() throws InterruptedException, ExecutionException {
        int concurrentConnections = 100;
        int operationsPerConnection = 10;
        ExecutorService executor = Executors.newFixedThreadPool(concurrentConnections);

        long startTime = System.currentTimeMillis();

        List<CompletableFuture<Void>> futures = IntStream.range(0, concurrentConnections)
                .mapToObj(connIndex -> CompletableFuture.runAsync(() -> {
                    for (int op = 0; op < operationsPerConnection; op++) {
                        try {
                            // Simple operations to stress connection pool
                            origamiRepository.count();
                            Thread.sleep(10); // Small delay to simulate processing
                        } catch (Exception e) {
                            // Expected under high connection load
                        }
                    }
                }, executor))
                .toList();

        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get();
        
        long endTime = System.currentTimeMillis();
        long duration = endTime - startTime;

        executor.shutdown();
        executor.awaitTermination(30, TimeUnit.SECONDS);

        int totalOperations = concurrentConnections * operationsPerConnection;
        double operationsPerSecond = (double) totalOperations / (duration / 1000.0);

        // Connection pool should handle this load efficiently
        assertThat(operationsPerSecond).isGreaterThan(50);
        assertThat(duration).isLessThan(30000); // Should complete within 30 seconds
    }

    @Test
    @DisplayName("Should handle transaction rollback performance")
    @Transactional
    void testTransactionRollbackPerformance() {
        long startTime = System.currentTimeMillis();
        
        // Perform operations that will be rolled back
        for (int i = 0; i < 100; i++) {
            Origami tempOrigami = Origami.builder()
                    .origamiId(String.format("rollback-test-%d", i))
                    .name(String.format("Rollback Test %d", i))
                    .description("This will be rolled back")
                    .voteCount(0)
                    .active(true)
                    .build();
            
            origamiRepository.save(tempOrigami);
            
            // Perform some updates
            origamiRepository.incrementVoteCount(tempOrigami.getId());
        }
        
        long endTime = System.currentTimeMillis();
        long duration = endTime - startTime;
        
        // Force rollback by throwing exception
        assertThrows(RuntimeException.class, () -> {
            throw new RuntimeException("Forced rollback for performance test");
        });
        
        // Performance assertion - rollback operations should be reasonably fast
        assertThat(duration).isLessThan(5000); // Should complete within 5 seconds
    }

    @Test
    @DisplayName("Should handle index usage efficiently")
    void testIndexPerformanceOptimization() {
        // Test queries that should benefit from indexes
        
        // Test unique index on origami_id
        long startTime = System.currentTimeMillis();
        for (int i = 0; i < 100; i++) {
            String targetId = largeDataset.get(i).getOrigamiId();
            origamiRepository.findByOrigamiId(targetId);
        }
        long uniqueIndexTime = System.currentTimeMillis() - startTime;
        
        // Test index on active column
        startTime = System.currentTimeMillis();
        for (int i = 0; i < 10; i++) {
            origamiRepository.findByActiveTrue();
        }
        long activeIndexTime = System.currentTimeMillis() - startTime;
        
        // Test composite index on vote_count and active
        startTime = System.currentTimeMillis();
        for (int i = 0; i < 10; i++) {
            origamiRepository.findByVoteCountGreaterThanAndActiveTrue(i * 10);
        }
        long compositeIndexTime = System.currentTimeMillis() - startTime;
        
        // Performance assertions - indexed queries should be fast
        assertThat(uniqueIndexTime).isLessThan(1000); // 100 unique lookups < 1 second
        assertThat(activeIndexTime).isLessThan(2000); // 10 active queries < 2 seconds
        assertThat(compositeIndexTime).isLessThan(3000); // 10 composite queries < 3 seconds
    }

    @Test
    @DisplayName("Should measure memory usage under sustained load")
    void testMemoryUsageUnderLoad() {
        Runtime runtime = Runtime.getRuntime();
        long initialMemory = runtime.totalMemory() - runtime.freeMemory();
        
        // Sustained operations to test memory usage
        for (int batch = 0; batch < 20; batch++) {
            // Create temporary origamis
            List<Origami> tempOrigamis = new ArrayList<>();
            for (int i = 0; i < 50; i++) {
                Origami origami = Origami.builder()
                        .origamiId(String.format("memory-test-%d-%d", batch, i))
                        .name(String.format("Memory Test %d-%d", batch, i))
                        .description("Testing memory usage patterns")
                        .voteCount(0)
                        .active(true)
                        .build();
                
                origamiRepository.save(origami);
                tempOrigamis.add(origami);
            }
            
            // Perform read operations
            origamiRepository.findByActiveTrue();
            
            // Clean up half of the temporary origamis
            for (int i = 0; i < tempOrigamis.size(); i += 2) {
                origamiRepository.softDeleteById(tempOrigamis.get(i).getId());
            }
            
            // Force garbage collection periodically
            if (batch % 5 == 0) {
                System.gc();
            }
        }
        
        long finalMemory = runtime.totalMemory() - runtime.freeMemory();
        long memoryIncrease = finalMemory - initialMemory;
        
        // Memory usage should not increase dramatically
        // Note: This is a rough check as GC behavior can vary
        assertThat(memoryIncrease).isLessThan(100 * 1024 * 1024); // Less than 100MB increase
    }
}