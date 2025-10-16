package com.example.voting.repository;

import com.example.voting.model.Origami;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration tests for OrigamiRepository using real PostgreSQL database via Testcontainers.
 * 
 * These tests validate database operations against a real PostgreSQL instance,
 * ensuring compatibility and testing database-specific features like transactions,
 * concurrency, and schema migrations.
 */
@DataJpaTest
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Transactional
class OrigamiRepositoryIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("testdb")
            .withUsername("testuser")
            .withPassword("testpass")
            .withInitScript("test-schema.sql");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.datasource.driver-class-name", () -> "org.postgresql.Driver");
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "create-drop");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.PostgreSQLDialect");
    }

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private OrigamiRepository origamiRepository;

    private Origami testOrigami1;
    private Origami testOrigami2;
    private Origami inactiveOrigami;

    @BeforeEach
    void setUp() {
        // Create test data
        testOrigami1 = Origami.builder()
                .origamiId("integration-crane-001")
                .name("Integration Test Origami Crane")
                .description("Beautiful crane for integration testing with PostgreSQL")
                .imageUrl("/static/images/integration-crane.png")
                .voteCount(15)
                .active(true)
                .build();

        testOrigami2 = Origami.builder()
                .origamiId("integration-butterfly-002")
                .name("Integration Test Origami Butterfly")
                .description("Colorful butterfly for PostgreSQL testing")
                .imageUrl("/static/images/integration-butterfly.png")
                .voteCount(25)
                .active(true)
                .build();

        inactiveOrigami = Origami.builder()
                .origamiId("integration-inactive-003")
                .name("Inactive Integration Test Origami")
                .description("This origami is inactive in PostgreSQL")
                .imageUrl("/static/images/integration-inactive.png")
                .voteCount(8)
                .active(false)
                .build();

        // Persist test data
        entityManager.persistAndFlush(testOrigami1);
        entityManager.persistAndFlush(testOrigami2);
        entityManager.persistAndFlush(inactiveOrigami);
    }

    @Test
    @DisplayName("Should connect to PostgreSQL container successfully")
    void testDatabaseConnection() {
        // Verify container is running
        assertThat(postgres.isRunning()).isTrue();
        
        // Verify we can query the database
        long count = origamiRepository.count();
        assertThat(count).isEqualTo(3); // 3 test origamis created in setUp
    }

    @Test
    @DisplayName("Should perform CRUD operations with PostgreSQL")
    void testCrudOperationsWithPostgreSQL() {
        // Create
        Origami newOrigami = Origami.builder()
                .origamiId("postgres-crud-001")
                .name("PostgreSQL CRUD Test")
                .description("Testing CRUD operations with real PostgreSQL")
                .voteCount(0)
                .active(true)
                .build();
        
        Origami saved = origamiRepository.save(newOrigami);
        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getCreatedAt()).isNotNull();
        assertThat(saved.getUpdatedAt()).isNotNull();

        // Read
        Optional<Origami> found = origamiRepository.findByOrigamiId("postgres-crud-001");
        assertThat(found).isPresent();
        assertThat(found.get().getName()).isEqualTo("PostgreSQL CRUD Test");

        // Update
        int updated = origamiRepository.updateOrigamiDetails(
                "postgres-crud-001",
                "Updated PostgreSQL CRUD Test",
                "Updated description for PostgreSQL",
                "/images/updated-postgres-crud.png"
        );
        assertThat(updated).isEqualTo(1);

        // Verify update
        Optional<Origami> updatedOrigami = origamiRepository.findByOrigamiId("postgres-crud-001");
        assertThat(updatedOrigami).isPresent();
        assertThat(updatedOrigami.get().getName()).isEqualTo("Updated PostgreSQL CRUD Test");

        // Delete (soft delete)
        int deleted = origamiRepository.softDeleteByOrigamiId("postgres-crud-001");
        assertThat(deleted).isEqualTo(1);

        // Verify soft delete
        Optional<Origami> softDeleted = origamiRepository.findByOrigamiIdAndActiveTrue("postgres-crud-001");
        assertThat(softDeleted).isEmpty();

        // But should still exist in database
        Optional<Origami> stillExists = origamiRepository.findByOrigamiId("postgres-crud-001");
        assertThat(stillExists).isPresent();
        assertThat(stillExists.get().getActive()).isFalse();
    }

    @Test
    @DisplayName("Should handle PostgreSQL-specific data types and constraints")
    void testPostgreSQLSpecificFeatures() {
        // Test with PostgreSQL-specific timestamp precision
        Origami timestampTest = Origami.builder()
                .origamiId("postgres-timestamp-001")
                .name("Timestamp Test")
                .description("Testing PostgreSQL timestamp precision")
                .voteCount(0)
                .active(true)
                .build();

        Origami saved = origamiRepository.save(timestampTest);
        
        // PostgreSQL should preserve microsecond precision
        assertThat(saved.getCreatedAt()).isNotNull();
        assertThat(saved.getUpdatedAt()).isNotNull();
        
        // Test unique constraint on origami_id
        Origami duplicate = Origami.builder()
                .origamiId("postgres-timestamp-001") // Same ID
                .name("Duplicate Test")
                .description("This should fail due to unique constraint")
                .voteCount(0)
                .active(true)
                .build();

        assertThrows(Exception.class, () -> {
            origamiRepository.saveAndFlush(duplicate);
        });
    }

    @Test
    @DisplayName("Should handle concurrent operations with PostgreSQL")
    void testConcurrentOperationsWithPostgreSQL() throws InterruptedException, ExecutionException {
        // Given
        String origamiId = testOrigami1.getOrigamiId();
        int initialVoteCount = testOrigami1.getVoteCount();
        int numberOfThreads = 10;
        int incrementsPerThread = 5;

        ExecutorService executor = Executors.newFixedThreadPool(numberOfThreads);

        // When - Execute concurrent vote increments against PostgreSQL
        List<CompletableFuture<Integer>> futures = IntStream.range(0, numberOfThreads)
                .mapToObj(i -> CompletableFuture.supplyAsync(() -> {
                    int successfulIncrements = 0;
                    for (int j = 0; j < incrementsPerThread; j++) {
                        try {
                            int updated = origamiRepository.incrementVoteCountByOrigamiId(origamiId);
                            if (updated > 0) {
                                successfulIncrements++;
                            }
                            // Small delay to increase chance of concurrent access
                            Thread.sleep(1);
                        } catch (Exception e) {
                            // Expected in concurrent scenarios
                        }
                    }
                    return successfulIncrements;
                }, executor))
                .toList();

        // Wait for all futures to complete
        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get();

        executor.shutdown();
        executor.awaitTermination(10, TimeUnit.SECONDS);

        // Then - Verify final vote count with PostgreSQL
        entityManager.refresh(testOrigami1);
        int expectedTotalIncrements = numberOfThreads * incrementsPerThread;
        assertThat(testOrigami1.getVoteCount()).isEqualTo(initialVoteCount + expectedTotalIncrements);
    }

    @Test
    @DisplayName("Should handle large datasets efficiently with PostgreSQL")
    void testLargeDatasetPerformance() {
        // Given - Create a larger dataset
        int batchSize = 100;
        
        // Create origamis in batches
        for (int batch = 0; batch < 5; batch++) {
            for (int i = 0; i < batchSize; i++) {
                Origami origami = Origami.builder()
                        .origamiId(String.format("perf-test-%03d-%03d", batch, i))
                        .name(String.format("Performance Test Origami %d-%d", batch, i))
                        .description("Testing PostgreSQL performance with larger datasets")
                        .voteCount(i % 50) // Vary vote counts
                        .active(i % 10 != 0) // 90% active
                        .build();
                
                entityManager.persist(origami);
                
                // Flush periodically to avoid memory issues
                if (i % 20 == 0) {
                    entityManager.flush();
                }
            }
            entityManager.flush();
            entityManager.clear();
        }

        // When - Perform queries on large dataset
        long startTime = System.currentTimeMillis();
        
        List<Origami> activeOrigamis = origamiRepository.findByActiveTrue();
        List<Origami> highVoteOrigamis = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(30);
        
        long endTime = System.currentTimeMillis();
        long queryTime = endTime - startTime;

        // Then - Verify results and performance
        assertThat(activeOrigamis.size()).isGreaterThan(400); // Should have ~450 active (90% of 500)
        assertThat(highVoteOrigamis.size()).isGreaterThan(80); // Should have ~90 with votes > 30
        assertThat(queryTime).isLessThan(5000); // Should complete within 5 seconds
    }

    @Test
    @DisplayName("Should handle PostgreSQL transaction isolation correctly")
    void testTransactionIsolation() {
        // Given
        String origamiId = testOrigami1.getOrigamiId();
        int initialVoteCount = testOrigami1.getVoteCount();

        // When - Perform operations in separate transactions
        // First transaction: increment vote count
        origamiRepository.incrementVoteCountByOrigamiId(origamiId);
        
        // Second transaction: update details
        origamiRepository.updateOrigamiDetails(
                origamiId,
                "Updated in Transaction Test",
                "Description updated in transaction test",
                "/images/transaction-test.png"
        );

        // Then - Both operations should be committed
        entityManager.refresh(testOrigami1);
        assertThat(testOrigami1.getVoteCount()).isEqualTo(initialVoteCount + 1);
        assertThat(testOrigami1.getName()).isEqualTo("Updated in Transaction Test");
    }

    @Test
    @DisplayName("Should handle PostgreSQL-specific query optimizations")
    void testQueryOptimizations() {
        // Given - Create origamis with specific patterns for testing indexes
        for (int i = 0; i < 50; i++) {
            Origami origami = Origami.builder()
                    .origamiId(String.format("query-opt-%03d", i))
                    .name(i % 2 == 0 ? "Even Origami " + i : "Odd Origami " + i)
                    .description("Query optimization test origami")
                    .voteCount(i)
                    .active(true)
                    .build();
            entityManager.persist(origami);
        }
        entityManager.flush();

        // When - Execute queries that should benefit from indexes
        long startTime = System.currentTimeMillis();
        
        // Query by origami_id (should use unique index)
        Optional<Origami> byId = origamiRepository.findByOrigamiId("query-opt-025");
        
        // Query by vote count range (should use index on vote_count)
        List<Origami> byVoteRange = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(40);
        
        // Query by name pattern (should use index on name if exists)
        List<Origami> byNamePattern = origamiRepository.findByNameContainingIgnoreCase("Even");
        
        long endTime = System.currentTimeMillis();
        long queryTime = endTime - startTime;

        // Then - Verify results and performance
        assertThat(byId).isPresent();
        assertThat(byId.get().getName()).isEqualTo("Odd Origami 25");
        
        assertThat(byVoteRange).hasSize(9); // 41, 42, 43, 44, 45, 46, 47, 48, 49
        
        assertThat(byNamePattern).hasSize(25); // All even-numbered origamis
        
        assertThat(queryTime).isLessThan(1000); // Should be fast with proper indexing
    }

    @Nested
    @DisplayName("Data Synchronization Integration Tests")
    class DataSynchronizationIntegrationTests {

        @Test
        @DisplayName("Should synchronize data between catalogue and voting services")
        void testCatalogueVotingSynchronization() {
            // Given - Simulate data from catalogue service
            String catalogueOrigamiId = "catalogue-sync-001";
            
            // Create origami as if it came from catalogue service
            Origami catalogueOrigami = Origami.builder()
                    .origamiId(catalogueOrigamiId)
                    .name("Catalogue Origami")
                    .description("Origami synchronized from catalogue service")
                    .imageUrl("/images/catalogue-origami.png")
                    .voteCount(0) // New from catalogue, no votes yet
                    .active(true)
                    .build();

            origamiRepository.save(catalogueOrigami);

            // When - Simulate voting activity
            // Multiple users vote for this origami
            for (int i = 0; i < 10; i++) {
                origamiRepository.incrementVoteCountByOrigamiId(catalogueOrigamiId);
            }

            // Simulate catalogue service updating the origami details
            origamiRepository.updateOrigamiDetails(
                    catalogueOrigamiId,
                    "Updated Catalogue Origami",
                    "Updated description from catalogue service",
                    "/images/updated-catalogue-origami.png"
            );

            // Then - Verify synchronization worked correctly
            Optional<Origami> synchronizedOrigami = origamiRepository.findByOrigamiId(catalogueOrigamiId);
            assertThat(synchronizedOrigami).isPresent();
            
            Origami syncedOrigami = synchronizedOrigami.get();
            assertThat(syncedOrigami.getName()).isEqualTo("Updated Catalogue Origami");
            assertThat(syncedOrigami.getDescription()).isEqualTo("Updated description from catalogue service");
            assertThat(syncedOrigami.getVoteCount()).isEqualTo(10); // Votes preserved during sync
            assertThat(syncedOrigami.getActive()).isTrue();
        }

        @Test
        @DisplayName("Should handle bulk synchronization from catalogue service")
        void testBulkSynchronizationFromCatalogue() {
            // Given - Simulate bulk data from catalogue service
            List<String> catalogueOrigamiIds = List.of(
                    "bulk-catalogue-001",
                    "bulk-catalogue-002",
                    "bulk-catalogue-003",
                    "bulk-catalogue-004",
                    "bulk-catalogue-005"
            );

            // Create origamis as if they came from catalogue service
            for (int i = 0; i < catalogueOrigamiIds.size(); i++) {
                String id = catalogueOrigamiIds.get(i);
                Origami origami = Origami.builder()
                        .origamiId(id)
                        .name("Bulk Catalogue Origami " + (i + 1))
                        .description("Bulk synchronized origami from catalogue")
                        .imageUrl("/images/bulk-catalogue-" + (i + 1) + ".png")
                        .voteCount(i * 2) // Varying vote counts
                        .active(true)
                        .build();
                origamiRepository.save(origami);
            }

            // When - Simulate bulk update from catalogue service
            for (int i = 0; i < catalogueOrigamiIds.size(); i++) {
                String id = catalogueOrigamiIds.get(i);
                origamiRepository.updateOrigamiDetails(
                        id,
                        "Updated Bulk Catalogue Origami " + (i + 1),
                        "Updated bulk description from catalogue",
                        "/images/updated-bulk-catalogue-" + (i + 1) + ".png"
                );
            }

            // Then - Verify all were updated correctly
            for (int i = 0; i < catalogueOrigamiIds.size(); i++) {
                String id = catalogueOrigamiIds.get(i);
                Optional<Origami> updated = origamiRepository.findByOrigamiId(id);
                
                assertThat(updated).isPresent();
                assertThat(updated.get().getName()).isEqualTo("Updated Bulk Catalogue Origami " + (i + 1));
                assertThat(updated.get().getDescription()).isEqualTo("Updated bulk description from catalogue");
                assertThat(updated.get().getVoteCount()).isEqualTo(i * 2); // Vote counts preserved
            }
        }

        @Test
        @DisplayName("Should identify origamis needing synchronization with catalogue")
        void testIdentifyOrigamisNeedingSyncWithCatalogue() {
            // Given - Create origamis with different update times
            LocalDateTime oldTime = LocalDateTime.now().minusHours(3);
            LocalDateTime recentTime = LocalDateTime.now().minusMinutes(15);
            LocalDateTime syncThreshold = LocalDateTime.now().minusHours(1);

            // Create origami that needs sync (old)
            Origami oldOrigami = Origami.builder()
                    .origamiId("needs-sync-001")
                    .name("Needs Sync Origami")
                    .description("This origami needs synchronization")
                    .voteCount(5)
                    .active(true)
                    .build();
            origamiRepository.save(oldOrigami);

            // Manually update timestamp to simulate old data
            entityManager.getEntityManager()
                    .createNativeQuery("UPDATE origami SET updated_at = ? WHERE origami_id = ?")
                    .setParameter(1, oldTime)
                    .setParameter(2, "needs-sync-001")
                    .executeUpdate();

            // Create origami that doesn't need sync (recent)
            Origami recentOrigami = Origami.builder()
                    .origamiId("no-sync-needed-001")
                    .name("Recent Origami")
                    .description("This origami is up to date")
                    .voteCount(3)
                    .active(true)
                    .build();
            origamiRepository.save(recentOrigami);

            entityManager.flush();
            entityManager.clear();

            // When - Find origamis needing sync
            List<Origami> needingSync = origamiRepository.findOrigamiNeedingSync(syncThreshold);

            // Then - Should identify the old origami
            assertThat(needingSync).hasSize(1);
            assertThat(needingSync.get(0).getOrigamiId()).isEqualTo("needs-sync-001");
        }

        @Test
        @DisplayName("Should handle synchronization conflicts gracefully")
        void testSynchronizationConflictHandling() {
            // Given - Origami that might have conflicts during sync
            String conflictOrigamiId = "conflict-handling-001";
            Origami conflictOrigami = Origami.builder()
                    .origamiId(conflictOrigamiId)
                    .name("Conflict Test Origami")
                    .description("Testing conflict handling during sync")
                    .voteCount(10)
                    .active(true)
                    .build();

            origamiRepository.save(conflictOrigami);

            // When - Simulate concurrent operations during sync
            // User votes while sync is happening
            origamiRepository.incrementVoteCountByOrigamiId(conflictOrigamiId);
            origamiRepository.incrementVoteCountByOrigamiId(conflictOrigamiId);

            // Catalogue service updates details
            origamiRepository.updateOrigamiDetails(
                    conflictOrigamiId,
                    "Sync Updated Conflict Test",
                    "Description updated during sync conflict test",
                    "/images/sync-conflict-test.png"
            );

            // More votes after sync
            origamiRepository.incrementVoteCountByOrigamiId(conflictOrigamiId);

            // Then - Both vote increments and sync updates should be preserved
            Optional<Origami> result = origamiRepository.findByOrigamiId(conflictOrigamiId);
            assertThat(result).isPresent();
            
            Origami resultOrigami = result.get();
            assertThat(resultOrigami.getName()).isEqualTo("Sync Updated Conflict Test");
            assertThat(resultOrigami.getDescription()).isEqualTo("Description updated during sync conflict test");
            assertThat(resultOrigami.getVoteCount()).isEqualTo(13); // 10 + 2 + 1 = 13
        }
    }

    @Nested
    @DisplayName("PostgreSQL Performance and Scalability Tests")
    class PostgreSQLPerformanceTests {

        @Test
        @DisplayName("Should handle high-volume vote operations efficiently")
        void testHighVolumeVoteOperations() {
            // Given - Create origami for high-volume testing
            String highVolumeOrigamiId = "high-volume-001";
            Origami highVolumeOrigami = Origami.builder()
                    .origamiId(highVolumeOrigamiId)
                    .name("High Volume Test Origami")
                    .description("Testing high-volume vote operations")
                    .voteCount(0)
                    .active(true)
                    .build();

            origamiRepository.save(highVolumeOrigami);

            // When - Perform high volume of vote operations
            long startTime = System.currentTimeMillis();
            
            int numberOfVotes = 1000;
            for (int i = 0; i < numberOfVotes; i++) {
                origamiRepository.incrementVoteCountByOrigamiId(highVolumeOrigamiId);
            }
            
            long endTime = System.currentTimeMillis();
            long operationTime = endTime - startTime;

            // Then - Verify performance and correctness
            Optional<Origami> result = origamiRepository.findByOrigamiId(highVolumeOrigamiId);
            assertThat(result).isPresent();
            assertThat(result.get().getVoteCount()).isEqualTo(numberOfVotes);
            
            // Performance assertion - should complete within reasonable time
            assertThat(operationTime).isLessThan(10000); // 10 seconds for 1000 operations
        }

        @Test
        @DisplayName("Should handle complex queries efficiently on large dataset")
        void testComplexQueriesOnLargeDataset() {
            // Given - Create a large dataset with varied data
            int datasetSize = 1000;
            
            for (int i = 0; i < datasetSize; i++) {
                Origami origami = Origami.builder()
                        .origamiId(String.format("large-dataset-%04d", i))
                        .name(String.format("Dataset Origami %d", i))
                        .description("Large dataset test origami with index " + i)
                        .voteCount(i % 100) // Vote counts from 0 to 99
                        .active(i % 10 != 0) // 90% active
                        .build();
                
                entityManager.persist(origami);
                
                if (i % 100 == 0) {
                    entityManager.flush();
                }
            }
            entityManager.flush();
            entityManager.clear();

            // When - Execute complex queries
            long startTime = System.currentTimeMillis();
            
            // Complex query 1: Find top voted active origamis
            Pageable topTen = PageRequest.of(0, 10);
            List<Origami> topVoted = origamiRepository.findTopByVoteCount(topTen);
            
            // Complex query 2: Find origamis with vote count in specific range
            List<Origami> midRangeVotes = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(50);
            
            // Complex query 3: Get statistics
            Object[] stats = origamiRepository.getVoteCountStatistics();
            
            long endTime = System.currentTimeMillis();
            long queryTime = endTime - startTime;

            // Then - Verify results and performance
            assertThat(topVoted).hasSize(10);
            assertThat(topVoted.get(0).getVoteCount()).isGreaterThanOrEqualTo(topVoted.get(9).getVoteCount());
            
            assertThat(midRangeVotes.size()).isGreaterThan(400); // Should have many results
            
            assertThat(stats).hasSize(4);
            assertThat((Long) stats[3]).isGreaterThan(800L); // Count of active origamis
            
            // Performance assertion
            assertThat(queryTime).isLessThan(5000); // Should complete within 5 seconds
        }

        @Test
        @DisplayName("Should maintain data consistency under concurrent load")
        void testDataConsistencyUnderConcurrentLoad() throws InterruptedException, ExecutionException {
            // Given - Multiple origamis for concurrent testing
            List<String> origamiIds = List.of(
                    "concurrent-load-001",
                    "concurrent-load-002",
                    "concurrent-load-003"
            );

            for (String id : origamiIds) {
                Origami origami = Origami.builder()
                        .origamiId(id)
                        .name("Concurrent Load Test " + id)
                        .description("Testing concurrent load")
                        .voteCount(0)
                        .active(true)
                        .build();
                origamiRepository.save(origami);
            }

            // When - Execute concurrent operations
            ExecutorService executor = Executors.newFixedThreadPool(20);
            int operationsPerOrigami = 100;

            List<CompletableFuture<Void>> futures = origamiIds.stream()
                    .flatMap(origamiId -> IntStream.range(0, operationsPerOrigami)
                            .mapToObj(i -> CompletableFuture.runAsync(() -> {
                                try {
                                    // Mix of operations
                                    if (i % 3 == 0) {
                                        // Vote increment
                                        origamiRepository.incrementVoteCountByOrigamiId(origamiId);
                                    } else if (i % 3 == 1) {
                                        // Read operation
                                        origamiRepository.findByOrigamiId(origamiId);
                                    } else {
                                        // Update operation
                                        origamiRepository.updateOrigamiDetails(
                                                origamiId,
                                                "Updated " + origamiId + " " + i,
                                                "Updated description " + i,
                                                "/images/updated-" + origamiId + "-" + i + ".png"
                                        );
                                    }
                                } catch (Exception e) {
                                    // Expected in high concurrency scenarios
                                }
                            }, executor)))
                    .toList();

            CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get();
            executor.shutdown();
            executor.awaitTermination(30, TimeUnit.SECONDS);

            // Then - Verify data consistency
            for (String origamiId : origamiIds) {
                Optional<Origami> result = origamiRepository.findByOrigamiId(origamiId);
                assertThat(result).isPresent();
                
                Origami origami = result.get();
                assertThat(origami.getVoteCount()).isGreaterThanOrEqualTo(0);
                assertThat(origami.getName()).startsWith("Updated " + origamiId);
                assertThat(origami.getActive()).isTrue();
            }
        }
    }
}