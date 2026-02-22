package com.example.voting.repository;

import com.example.voting.model.Origami;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.transaction.TestTransaction;
import org.springframework.transaction.annotation.Transactional;

import jakarta.persistence.EntityManager;
import jakarta.persistence.Query;
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
 * PostgreSQL compatibility tests for OrigamiRepository.
 * 
 * These tests use H2 in PostgreSQL compatibility mode to test PostgreSQL-specific
 * features without requiring Docker containers. This provides a fast way to validate
 * PostgreSQL compatibility and database operations.
 */
@DataJpaTest
@ActiveProfiles("test")
@TestPropertySource(properties = {
    "spring.datasource.url=jdbc:h2:mem:testdb;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH",
    "spring.jpa.database-platform=org.hibernate.dialect.PostgreSQLDialect",
    "spring.jpa.hibernate.ddl-auto=create-drop"
})
@Transactional
class OrigamiRepositoryPostgreSQLCompatibilityTest {

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private OrigamiRepository origamiRepository;

    private Origami testOrigami1;
    private Origami testOrigami2;
    private Origami inactiveOrigami;

    @BeforeEach
    void setUp() {
        // Clean up any previously committed data from concurrent tests
        origamiRepository.deleteAllInBatch();
        entityManager.flush();
        entityManager.clear();

        // Create test data
        testOrigami1 = Origami.builder()
                .origamiId("postgres-compat-crane-001")
                .name("PostgreSQL Compatibility Test Crane")
                .description("Testing PostgreSQL compatibility features")
                .imageUrl("/static/images/postgres-crane.png")
                .voteCount(20)
                .active(true)
                .build();

        testOrigami2 = Origami.builder()
                .origamiId("postgres-compat-butterfly-002")
                .name("PostgreSQL Compatibility Test Butterfly")
                .description("Testing PostgreSQL compatibility with H2")
                .imageUrl("/static/images/postgres-butterfly.png")
                .voteCount(35)
                .active(true)
                .build();

        inactiveOrigami = Origami.builder()
                .origamiId("postgres-compat-inactive-003")
                .name("Inactive PostgreSQL Compatibility Test")
                .description("This origami is inactive for PostgreSQL compatibility testing")
                .imageUrl("/static/images/postgres-inactive.png")
                .voteCount(12)
                .active(false)
                .build();

        // Persist test data
        entityManager.persistAndFlush(testOrigami1);
        entityManager.persistAndFlush(testOrigami2);
        entityManager.persistAndFlush(inactiveOrigami);
    }

    @Test
    @DisplayName("Should validate PostgreSQL compatibility mode is active")
    void testPostgreSQLCompatibilityMode() {
        // Verify H2 is running in PostgreSQL mode
        EntityManager em = entityManager.getEntityManager();
        Query query = em.createNativeQuery("SELECT H2VERSION()");
        String h2Version = (String) query.getSingleResult();
        
        assertThat(h2Version).isNotNull();
        
        // Test PostgreSQL-specific SQL features
        Query pgQuery = em.createNativeQuery("SELECT COUNT(*) FROM origami WHERE active = true");
        Number count = (Number) pgQuery.getSingleResult();
        assertThat(count.intValue()).isEqualTo(2);
    }

    @Test
    @DisplayName("Should handle PostgreSQL-style case sensitivity")
    void testPostgreSQLCaseSensitivity() {
        // PostgreSQL is case-sensitive for identifiers unless quoted
        // H2 in PostgreSQL mode should behave similarly
        
        EntityManager em = entityManager.getEntityManager();
        
        // Test case-insensitive table name (should work)
        Query query1 = em.createNativeQuery("SELECT COUNT(*) FROM origami");
        Number count1 = (Number) query1.getSingleResult();
        assertThat(count1.intValue()).isEqualTo(3);
        
        // Test case-insensitive column name (should work)
        Query query2 = em.createNativeQuery("SELECT COUNT(*) FROM origami WHERE active = true");
        Number count2 = (Number) query2.getSingleResult();
        assertThat(count2.intValue()).isEqualTo(2);
    }

    @Test
    @DisplayName("Should handle PostgreSQL-style boolean operations")
    void testPostgreSQLBooleanOperations() {
        // Test boolean operations that are PostgreSQL-specific
        List<Origami> activeOrigamis = origamiRepository.findByActiveTrue();
        assertThat(activeOrigamis).hasSize(2);
        
        // Test with native query using PostgreSQL boolean syntax
        EntityManager em = entityManager.getEntityManager();
        Query query = em.createNativeQuery(
            "SELECT * FROM origami WHERE active = TRUE AND vote_count > ?", 
            Origami.class
        );
        query.setParameter(1, 15);
        
        @SuppressWarnings("unchecked")
        List<Origami> results = query.getResultList();
        assertThat(results).hasSize(2); // Both active origamis have vote_count > 15
    }

    @Test
    @DisplayName("Should handle PostgreSQL-style string operations")
    void testPostgreSQLStringOperations() {
        // Test case-insensitive string matching (PostgreSQL ILIKE equivalent)
        List<Origami> craneOrigamis = origamiRepository.findByNameContainingIgnoreCase("crane");
        assertThat(craneOrigamis).hasSize(1);
        assertThat(craneOrigamis.get(0).getOrigamiId()).isEqualTo("postgres-compat-crane-001");
        
        // Test with native query using PostgreSQL-style string functions
        EntityManager em = entityManager.getEntityManager();
        Query query = em.createNativeQuery(
            "SELECT * FROM origami WHERE LOWER(name) LIKE LOWER(?)", 
            Origami.class
        );
        query.setParameter(1, "%butterfly%");
        
        @SuppressWarnings("unchecked")
        List<Origami> results = query.getResultList();
        assertThat(results).hasSize(1);
        assertThat(results.get(0).getOrigamiId()).isEqualTo("postgres-compat-butterfly-002");
    }

    @Test
    @DisplayName("Should handle PostgreSQL-style timestamp operations")
    void testPostgreSQLTimestampOperations() {
        // Test timestamp operations that are PostgreSQL-specific
        LocalDateTime threshold = LocalDateTime.now().minusHours(1);
        
        // All test origamis should be created after the threshold
        List<Origami> recentOrigamis = origamiRepository.findByCreatedAtAfterAndActiveTrue(threshold);
        assertThat(recentOrigamis).hasSize(2); // Only active ones
        
        // Test with native query using PostgreSQL timestamp functions
        EntityManager em = entityManager.getEntityManager();
        Query query = em.createNativeQuery(
            "SELECT COUNT(*) FROM origami WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '1' HOUR"
        );
        Number count = (Number) query.getSingleResult();
        assertThat(count.intValue()).isEqualTo(3); // All origamis created recently
    }

    @Test
    @DisplayName("Should handle PostgreSQL-style numeric operations")
    void testPostgreSQLNumericOperations() {
        // Test numeric operations and aggregations
        Object[] stats = origamiRepository.getVoteCountStatistics();
        
        assertThat(stats).hasSize(4);
        Integer minVotes = (Integer) stats[0];
        Integer maxVotes = (Integer) stats[1];
        Double avgVotes = (Double) stats[2];
        Long count = (Long) stats[3];
        
        assertThat(minVotes).isEqualTo(20); // testOrigami1 has lowest votes among active
        assertThat(maxVotes).isEqualTo(35); // testOrigami2 has highest votes
        assertThat(avgVotes).isEqualTo(27.5); // (20 + 35) / 2 = 27.5
        assertThat(count).isEqualTo(2L); // 2 active origamis
        
        // Test with native PostgreSQL-style numeric query
        EntityManager em = entityManager.getEntityManager();
        Query query = em.createNativeQuery(
            "SELECT ROUND(AVG(CAST(vote_count AS DECIMAL)), 2) FROM origami WHERE active = true"
        );
        Number avgResult = (Number) query.getSingleResult();
        assertThat(avgResult.doubleValue()).isEqualTo(27.5);
    }

    @Test
    @DisplayName("Should handle PostgreSQL-style transaction isolation")
    void testPostgreSQLTransactionIsolation() {
        // Test transaction behavior similar to PostgreSQL
        String origamiId = testOrigami1.getOrigamiId();
        int initialVoteCount = testOrigami1.getVoteCount();
        
        // Perform multiple operations in the same transaction
        origamiRepository.incrementVoteCountByOrigamiId(origamiId);
        origamiRepository.updateOrigamiDetails(
            origamiId,
            "Updated in PostgreSQL Transaction Test",
            "Description updated in PostgreSQL compatibility test",
            "/images/postgres-transaction-test.png"
        );
        
        // Both operations should be visible within the same transaction
        Origami freshOrigami = origamiRepository.findByOrigamiId(origamiId).orElseThrow();
        assertThat(freshOrigami.getVoteCount()).isEqualTo(initialVoteCount + 1);
        assertThat(freshOrigami.getName()).isEqualTo("Updated in PostgreSQL Transaction Test");
    }

    @Test
    @DisplayName("Should handle concurrent operations with PostgreSQL-style locking")
    void testPostgreSQLConcurrentOperations() throws InterruptedException, ExecutionException {
        // Test concurrent operations that would work with PostgreSQL row-level locking
        String origamiId = testOrigami1.getOrigamiId();
        int initialVoteCount = testOrigami1.getVoteCount();
        int numberOfThreads = 5;
        int incrementsPerThread = 3;

        // Commit setup data so it is visible to concurrent threads
        TestTransaction.flagForCommit();
        TestTransaction.end();

        ExecutorService executor = Executors.newFixedThreadPool(numberOfThreads);

        // Execute concurrent vote increments
        List<CompletableFuture<Integer>> futures = IntStream.range(0, numberOfThreads)
                .mapToObj(i -> CompletableFuture.supplyAsync(() -> {
                    int successfulIncrements = 0;
                    for (int j = 0; j < incrementsPerThread; j++) {
                        try {
                            int updated = origamiRepository.incrementVoteCountByOrigamiId(origamiId);
                            if (updated > 0) {
                                successfulIncrements++;
                            }
                            Thread.sleep(1); // Small delay
                        } catch (Exception e) {
                            // Expected in concurrent scenarios
                        }
                    }
                    return successfulIncrements;
                }, executor))
                .toList();

        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get();
        executor.shutdown();
        executor.awaitTermination(5, TimeUnit.SECONDS);

        // Start new transaction for verification
        TestTransaction.start();

        // Verify final vote count
        Optional<Origami> result = origamiRepository.findByOrigamiId(origamiId);
        assertThat(result).isPresent();
        int expectedTotalIncrements = numberOfThreads * incrementsPerThread;
        assertThat(result.get().getVoteCount()).isEqualTo(initialVoteCount + expectedTotalIncrements);
    }

    @Nested
    @DisplayName("PostgreSQL Data Synchronization Compatibility Tests")
    class PostgreSQLDataSynchronizationTests {

        @Test
        @DisplayName("Should handle bulk operations with PostgreSQL-style performance")
        void testPostgreSQLBulkOperations() {
            // Create multiple origamis for bulk testing
            int batchSize = 50;
            
            for (int i = 0; i < batchSize; i++) {
                Origami origami = Origami.builder()
                        .origamiId(String.format("bulk-postgres-%03d", i))
                        .name(String.format("Bulk PostgreSQL Test %d", i))
                        .description("Testing PostgreSQL bulk operations")
                        .voteCount(i % 20) // Vary vote counts
                        .active(i % 5 != 0) // 80% active
                        .build();
                
                entityManager.persist(origami);
                
                // Flush periodically like PostgreSQL batch processing
                if (i % 10 == 0) {
                    entityManager.flush();
                }
            }
            entityManager.flush();
            entityManager.clear();

            // Test bulk query performance
            long startTime = System.currentTimeMillis();
            
            List<Origami> activeOrigamis = origamiRepository.findByActiveTrue();
            List<Origami> highVoteOrigamis = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(10);
            
            long endTime = System.currentTimeMillis();
            long queryTime = endTime - startTime;

            // Verify results
            assertThat(activeOrigamis.size()).isGreaterThan(40); // Should have ~40 active (80% of 50)
            assertThat(highVoteOrigamis.size()).isGreaterThan(15); // Should have some with votes > 10
            assertThat(queryTime).isLessThan(2000); // Should be reasonably fast
        }

        @Test
        @DisplayName("Should handle PostgreSQL-style data synchronization patterns")
        void testPostgreSQLSynchronizationPatterns() {
            // Test synchronization patterns common in PostgreSQL applications
            String syncOrigamiId = "postgres-sync-001";
            
            // Create origami as if synchronized from catalogue service
            Origami syncOrigami = Origami.builder()
                    .origamiId(syncOrigamiId)
                    .name("PostgreSQL Sync Test")
                    .description("Testing PostgreSQL synchronization patterns")
                    .voteCount(0)
                    .active(true)
                    .build();

            origamiRepository.save(syncOrigami);

            // Simulate voting activity
            for (int i = 0; i < 5; i++) {
                origamiRepository.incrementVoteCountByOrigamiId(syncOrigamiId);
            }

            // Simulate catalogue service update (should preserve votes)
            origamiRepository.updateOrigamiDetails(
                    syncOrigamiId,
                    "Updated PostgreSQL Sync Test",
                    "Updated description from catalogue service",
                    "/images/updated-postgres-sync.png"
            );

            // Verify synchronization preserved votes
            Optional<Origami> result = origamiRepository.findByOrigamiId(syncOrigamiId);
            assertThat(result).isPresent();
            
            Origami resultOrigami = result.get();
            assertThat(resultOrigami.getName()).isEqualTo("Updated PostgreSQL Sync Test");
            assertThat(resultOrigami.getVoteCount()).isEqualTo(5); // Votes preserved
        }

        @Test
        @DisplayName("Should handle PostgreSQL-style conflict resolution")
        void testPostgreSQLConflictResolution() {
            // Test conflict resolution patterns used in PostgreSQL
            String conflictOrigamiId = "postgres-conflict-001";
            
            Origami conflictOrigami = Origami.builder()
                    .origamiId(conflictOrigamiId)
                    .name("PostgreSQL Conflict Test")
                    .description("Testing PostgreSQL conflict resolution")
                    .voteCount(10)
                    .active(true)
                    .build();

            origamiRepository.save(conflictOrigami);

            // Simulate concurrent operations
            // User votes
            origamiRepository.incrementVoteCountByOrigamiId(conflictOrigamiId);
            origamiRepository.incrementVoteCountByOrigamiId(conflictOrigamiId);

            // Catalogue service updates details
            origamiRepository.updateOrigamiDetails(
                    conflictOrigamiId,
                    "Updated PostgreSQL Conflict Test",
                    "Updated during conflict resolution test",
                    "/images/postgres-conflict-resolved.png"
            );

            // More votes after update
            origamiRepository.incrementVoteCountByOrigamiId(conflictOrigamiId);

            // Verify both updates and votes are preserved
            Optional<Origami> result = origamiRepository.findByOrigamiId(conflictOrigamiId);
            assertThat(result).isPresent();
            
            Origami resultOrigami = result.get();
            assertThat(resultOrigami.getName()).isEqualTo("Updated PostgreSQL Conflict Test");
            assertThat(resultOrigami.getVoteCount()).isEqualTo(13); // 10 + 2 + 1 = 13
        }

        @Test
        @DisplayName("Should identify origamis needing sync with PostgreSQL-style queries")
        void testPostgreSQLSyncIdentification() {
            // Test sync identification using PostgreSQL-style timestamp queries
            LocalDateTime oldTime = LocalDateTime.now().minusHours(2);
            LocalDateTime syncThreshold = LocalDateTime.now().minusHours(1);

            // Create origami that needs sync
            Origami needsSyncOrigami = Origami.builder()
                    .origamiId("postgres-needs-sync-001")
                    .name("PostgreSQL Needs Sync")
                    .description("This origami needs synchronization")
                    .voteCount(8)
                    .active(true)
                    .build();
            origamiRepository.save(needsSyncOrigami);

            // Manually update timestamp using PostgreSQL-style query
            EntityManager em = entityManager.getEntityManager();
            Query updateQuery = em.createNativeQuery(
                "UPDATE origami SET updated_at = ? WHERE origami_id = ?"
            );
            updateQuery.setParameter(1, oldTime);
            updateQuery.setParameter(2, "postgres-needs-sync-001");
            updateQuery.executeUpdate();

            entityManager.flush();
            entityManager.clear();

            // Find origamis needing sync using PostgreSQL-compatible query
            List<Origami> needingSync = origamiRepository.findOrigamiNeedingSync(syncThreshold);

            // Verify identification works
            assertThat(needingSync).hasSize(1);
            assertThat(needingSync.get(0).getOrigamiId()).isEqualTo("postgres-needs-sync-001");
        }
    }

    @Nested
    @DisplayName("PostgreSQL Performance Compatibility Tests")
    class PostgreSQLPerformanceCompatibilityTests {

        @Test
        @DisplayName("Should handle PostgreSQL-style index usage patterns")
        void testPostgreSQLIndexUsagePatterns() {
            // Create data that would benefit from PostgreSQL indexes
            for (int i = 0; i < 100; i++) {
                Origami origami = Origami.builder()
                        .origamiId(String.format("index-test-%03d", i))
                        .name(String.format("Index Test Origami %d", i))
                        .description("Testing PostgreSQL index usage patterns")
                        .voteCount(i)
                        .active(i % 10 != 0) // 90% active
                        .build();
                entityManager.persist(origami);
            }
            entityManager.flush();

            // Test queries that would use indexes in PostgreSQL
            long startTime = System.currentTimeMillis();
            
            // Primary key lookup (would use unique index)
            Optional<Origami> byId = origamiRepository.findByOrigamiId("index-test-050");
            
            // Range query (would use index on vote_count)
            List<Origami> highVotes = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(80);
            
            // Pattern matching (would use index on name if exists)
            List<Origami> namePattern = origamiRepository.findByNameContainingIgnoreCase("Index");
            
            long endTime = System.currentTimeMillis();
            long queryTime = endTime - startTime;

            // Verify results and reasonable performance
            assertThat(byId).isPresent();
            assertThat(highVotes.size()).isGreaterThan(15); // Should find many results
            assertThat(namePattern.size()).isGreaterThan(80); // Should find most origamis
            assertThat(queryTime).isLessThan(1000); // Should be reasonably fast
        }

        @Test
        @DisplayName("Should handle PostgreSQL-style aggregate operations")
        void testPostgreSQLAggregateOperations() {
            // Create varied data for aggregation testing
            for (int i = 0; i < 50; i++) {
                Origami origami = Origami.builder()
                        .origamiId(String.format("agg-test-%03d", i))
                        .name(String.format("Aggregate Test %d", i))
                        .description("Testing PostgreSQL aggregate operations")
                        .voteCount(i * 2) // Even vote counts: 0, 2, 4, ..., 98
                        .active(i % 3 != 0) // ~67% active
                        .build();
                entityManager.persist(origami);
            }
            entityManager.flush();

            // Test PostgreSQL-style aggregations
            Object[] stats = origamiRepository.getVoteCountStatistics();
            
            assertThat(stats).hasSize(4);
            Integer minVotes = (Integer) stats[0];
            Integer maxVotes = (Integer) stats[1];
            Double avgVotes = (Double) stats[2];
            Long count = (Long) stats[3];

            // Verify aggregation results
            assertThat(minVotes).isGreaterThanOrEqualTo(0);
            assertThat(maxVotes).isGreaterThan(minVotes);
            assertThat(avgVotes).isGreaterThan(0);
            assertThat(count).isGreaterThan(30); // Should have many active origamis

            // Test custom PostgreSQL-style aggregation
            EntityManager em = entityManager.getEntityManager();
            Query customAggQuery = em.createNativeQuery(
                "SELECT COUNT(*), SUM(vote_count), AVG(CAST(vote_count AS DECIMAL)) " +
                "FROM origami WHERE active = true AND vote_count > 20"
            );
            Object[] customStats = (Object[]) customAggQuery.getSingleResult();
            
            assertThat(customStats).hasSize(3);
            assertThat(((Number) customStats[0]).longValue()).isGreaterThan(0); // Count
            assertThat(((Number) customStats[1]).longValue()).isGreaterThan(0); // Sum
            assertThat(((Number) customStats[2]).doubleValue()).isGreaterThan(20); // Average
        }
    }
}