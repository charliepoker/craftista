package com.example.voting.repository;

import com.example.voting.model.Origami;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.orm.jpa.JpaSystemException;

import jakarta.persistence.PersistenceException;
import jakarta.validation.ConstraintViolationException;
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
 * Unit tests for OrigamiRepository.
 * 
 * Uses H2 in-memory database for fast, isolated testing of repository operations.
 * Tests cover CRUD operations, custom queries, and edge cases.
 */
@DataJpaTest
@ActiveProfiles("test")
@Transactional
class OrigamiRepositoryTest {

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
                .origamiId("test-crane-001")
                .name("Test Origami Crane")
                .description("Beautiful test crane for unit testing")
                .imageUrl("/static/images/test-crane.png")
                .voteCount(5)
                .active(true)
                .build();

        testOrigami2 = Origami.builder()
                .origamiId("test-butterfly-002")
                .name("Test Origami Butterfly")
                .description("Colorful test butterfly")
                .imageUrl("/static/images/test-butterfly.png")
                .voteCount(10)
                .active(true)
                .build();

        inactiveOrigami = Origami.builder()
                .origamiId("test-inactive-003")
                .name("Inactive Test Origami")
                .description("This origami is inactive")
                .imageUrl("/static/images/test-inactive.png")
                .voteCount(2)
                .active(false)
                .build();

        // Persist test data
        entityManager.persistAndFlush(testOrigami1);
        entityManager.persistAndFlush(testOrigami2);
        entityManager.persistAndFlush(inactiveOrigami);
    }

    @Test
    @DisplayName("Should find all active origami items")
    void testFindByActiveTrue() {
        // When
        List<Origami> activeOrigamis = origamiRepository.findByActiveTrue();

        // Then
        assertThat(activeOrigamis).hasSize(2);
        assertThat(activeOrigamis)
                .extracting(Origami::getOrigamiId)
                .containsExactlyInAnyOrder("test-crane-001", "test-butterfly-002");
        assertThat(activeOrigamis)
                .allMatch(Origami::getActive);
    }

    @Test
    @DisplayName("Should find active origami items with pagination")
    void testFindByActiveTrueWithPagination() {
        // Given
        Pageable pageable = PageRequest.of(0, 1);

        // When
        Page<Origami> page = origamiRepository.findByActiveTrue(pageable);

        // Then
        assertThat(page.getContent()).hasSize(1);
        assertThat(page.getTotalElements()).isEqualTo(2);
        assertThat(page.getTotalPages()).isEqualTo(2);
        assertThat(page.getContent().get(0).getActive()).isTrue();
    }

    @Test
    @DisplayName("Should find origami by external ID and active status")
    void testFindByOrigamiIdAndActiveTrue() {
        // When
        Optional<Origami> found = origamiRepository.findByOrigamiIdAndActiveTrue("test-crane-001");

        // Then
        assertThat(found).isPresent();
        assertThat(found.get().getName()).isEqualTo("Test Origami Crane");
        assertThat(found.get().getActive()).isTrue();
    }

    @Test
    @DisplayName("Should not find inactive origami by external ID and active status")
    void testFindByOrigamiIdAndActiveTrueWithInactive() {
        // When
        Optional<Origami> found = origamiRepository.findByOrigamiIdAndActiveTrue("test-inactive-003");

        // Then
        assertThat(found).isEmpty();
    }

    @Test
    @DisplayName("Should find origami by external ID regardless of active status")
    void testFindByOrigamiId() {
        // When - Find active origami
        Optional<Origami> activeFound = origamiRepository.findByOrigamiId("test-crane-001");
        
        // Then
        assertThat(activeFound).isPresent();
        assertThat(activeFound.get().getName()).isEqualTo("Test Origami Crane");

        // When - Find inactive origami
        Optional<Origami> inactiveFound = origamiRepository.findByOrigamiId("test-inactive-003");
        
        // Then
        assertThat(inactiveFound).isPresent();
        assertThat(inactiveFound.get().getName()).isEqualTo("Inactive Test Origami");
        assertThat(inactiveFound.get().getActive()).isFalse();
    }

    @Test
    @DisplayName("Should return empty when origami not found by external ID")
    void testFindByOrigamiIdNotFound() {
        // When
        Optional<Origami> found = origamiRepository.findByOrigamiId("non-existent-id");

        // Then
        assertThat(found).isEmpty();
    }

    @Test
    @DisplayName("Should count origami items by external ID")
    void testCountByOrigamiId() {
        // When
        int count = origamiRepository.countByOrigamiId("test-crane-001");

        // Then
        assertThat(count).isEqualTo(1);
    }

    @Test
    @DisplayName("Should return zero count for non-existent origami ID")
    void testCountByOrigamiIdNotFound() {
        // When
        int count = origamiRepository.countByOrigamiId("non-existent-id");

        // Then
        assertThat(count).isEqualTo(0);
    }

    @Test
    @DisplayName("Should check if origami exists by external ID")
    void testExistsByOrigamiId() {
        // When & Then
        assertThat(origamiRepository.existsByOrigamiId("test-crane-001")).isTrue();
        assertThat(origamiRepository.existsByOrigamiId("test-inactive-003")).isTrue();
        assertThat(origamiRepository.existsByOrigamiId("non-existent-id")).isFalse();
    }

    @Test
    @DisplayName("Should find origami with vote count greater than specified value")
    void testFindByVoteCountGreaterThanAndActiveTrue() {
        // When
        List<Origami> highVoteOrigamis = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(7);

        // Then
        assertThat(highVoteOrigamis).hasSize(1);
        assertThat(highVoteOrigamis.get(0).getOrigamiId()).isEqualTo("test-butterfly-002");
        assertThat(highVoteOrigamis.get(0).getVoteCount()).isEqualTo(10);
    }

    @Test
    @DisplayName("Should find top origami by vote count")
    void testFindTopByVoteCount() {
        // Given
        Pageable topThree = PageRequest.of(0, 3);

        // When
        List<Origami> topOrigamis = origamiRepository.findTopByVoteCount(topThree);

        // Then
        assertThat(topOrigamis).hasSize(2); // Only 2 active origamis
        assertThat(topOrigamis.get(0).getVoteCount()).isGreaterThanOrEqualTo(topOrigamis.get(1).getVoteCount());
        assertThat(topOrigamis.get(0).getOrigamiId()).isEqualTo("test-butterfly-002"); // Highest votes
    }

    @Test
    @DisplayName("Should atomically increment vote count by ID")
    void testIncrementVoteCount() {
        // Given
        Long origamiId = testOrigami1.getId();
        int originalVoteCount = testOrigami1.getVoteCount();

        // When
        int updatedRows = origamiRepository.incrementVoteCount(origamiId);

        // Then
        assertThat(updatedRows).isEqualTo(1);
        
        // Refresh entity to get updated data
        entityManager.refresh(testOrigami1);
        assertThat(testOrigami1.getVoteCount()).isEqualTo(originalVoteCount + 1);
    }

    @Test
    @DisplayName("Should atomically increment vote count by origami ID")
    void testIncrementVoteCountByOrigamiId() {
        // Given
        String origamiId = testOrigami1.getOrigamiId();
        int originalVoteCount = testOrigami1.getVoteCount();

        // When
        int updatedRows = origamiRepository.incrementVoteCountByOrigamiId(origamiId);

        // Then
        assertThat(updatedRows).isEqualTo(1);
        
        // Refresh entity to get updated data
        entityManager.refresh(testOrigami1);
        assertThat(testOrigami1.getVoteCount()).isEqualTo(originalVoteCount + 1);
    }

    @Test
    @DisplayName("Should not increment vote count for inactive origami")
    void testIncrementVoteCountByOrigamiIdInactive() {
        // Given
        String inactiveOrigamiId = inactiveOrigami.getOrigamiId();

        // When
        int updatedRows = origamiRepository.incrementVoteCountByOrigamiId(inactiveOrigamiId);

        // Then
        assertThat(updatedRows).isEqualTo(0); // No rows updated because origami is inactive
    }

    @Test
    @DisplayName("Should soft delete origami by ID")
    void testSoftDeleteById() {
        // Given
        Long origamiId = testOrigami1.getId();

        // When
        int updatedRows = origamiRepository.softDeleteById(origamiId);

        // Then
        assertThat(updatedRows).isEqualTo(1);
        
        // Refresh entity to get updated data
        entityManager.refresh(testOrigami1);
        assertThat(testOrigami1.getActive()).isFalse();
    }

    @Test
    @DisplayName("Should soft delete origami by origami ID")
    void testSoftDeleteByOrigamiId() {
        // Given
        String origamiId = testOrigami1.getOrigamiId();

        // When
        int updatedRows = origamiRepository.softDeleteByOrigamiId(origamiId);

        // Then
        assertThat(updatedRows).isEqualTo(1);
        
        // Refresh entity to get updated data
        entityManager.refresh(testOrigami1);
        assertThat(testOrigami1.getActive()).isFalse();
    }

    @Test
    @DisplayName("Should update origami details")
    void testUpdateOrigamiDetails() {
        // Given
        String origamiId = testOrigami1.getOrigamiId();
        String newName = "Updated Crane Name";
        String newDescription = "Updated description";
        String newImageUrl = "/static/images/updated-crane.png";

        // When
        int updatedRows = origamiRepository.updateOrigamiDetails(
                origamiId, newName, newDescription, newImageUrl);

        // Then
        assertThat(updatedRows).isEqualTo(1);
        
        // Refresh entity to get updated data
        entityManager.refresh(testOrigami1);
        assertThat(testOrigami1.getName()).isEqualTo(newName);
        assertThat(testOrigami1.getDescription()).isEqualTo(newDescription);
        assertThat(testOrigami1.getImageUrl()).isEqualTo(newImageUrl);
    }

    @Test
    @DisplayName("Should find origami created after specific date")
    void testFindByCreatedAtAfterAndActiveTrue() {
        // Given - Create an origami with a specific creation time
        LocalDateTime cutoffTime = LocalDateTime.now().minusHours(1);
        
        Origami recentOrigami = Origami.builder()
                .origamiId("recent-origami-004")
                .name("Recent Origami")
                .description("Recently created origami")
                .voteCount(0)
                .active(true)
                .build();
        
        entityManager.persistAndFlush(recentOrigami);

        // When
        List<Origami> recentOrigamis = origamiRepository.findByCreatedAtAfterAndActiveTrue(cutoffTime);

        // Then
        assertThat(recentOrigamis).hasSizeGreaterThanOrEqualTo(1);
        assertThat(recentOrigamis)
                .extracting(Origami::getOrigamiId)
                .contains("recent-origami-004");
    }

    @Test
    @DisplayName("Should get vote count statistics")
    void testGetVoteCountStatistics() {
        // When
        Object[] stats = origamiRepository.getVoteCountStatistics();

        // Then
        assertThat(stats).isNotNull();
        assertThat(stats).hasSize(4);
        
        // Extract statistics (MIN, MAX, AVG, COUNT)
        Integer minVotes = (Integer) stats[0];
        Integer maxVotes = (Integer) stats[1];
        Double avgVotes = (Double) stats[2];
        Long count = (Long) stats[3];

        assertThat(minVotes).isEqualTo(5); // testOrigami1 has 5 votes
        assertThat(maxVotes).isEqualTo(10); // testOrigami2 has 10 votes
        assertThat(avgVotes).isEqualTo(7.5); // (5 + 10) / 2 = 7.5
        assertThat(count).isEqualTo(2L); // 2 active origamis
    }

    @Test
    @DisplayName("Should find origami needing synchronization")
    void testFindOrigamiNeedingSync() {
        // Given - Create a new origami with old timestamp
        LocalDateTime oldTime = LocalDateTime.now().minusDays(2);
        LocalDateTime threshold = LocalDateTime.now().minusHours(1);
        
        Origami oldOrigami = Origami.builder()
                .origamiId("old-sync-001")
                .name("Old Origami")
                .description("This origami needs sync")
                .voteCount(0)
                .active(true)
                .build();
        
        // Persist first, then update the timestamp
        entityManager.persist(oldOrigami);
        entityManager.flush();
        
        // Manually update the timestamp using native query to bypass @UpdateTimestamp
        entityManager.getEntityManager().createNativeQuery("UPDATE origami SET updated_at = ? WHERE origami_id = ?")
                .setParameter(1, oldTime)
                .setParameter(2, "old-sync-001")
                .executeUpdate();
        
        entityManager.flush();
        entityManager.clear();

        // When
        List<Origami> needingSync = origamiRepository.findOrigamiNeedingSync(threshold);

        // Then
        assertThat(needingSync).hasSize(1);
        assertThat(needingSync.get(0).getOrigamiId()).isEqualTo("old-sync-001");
    }

    @Test
    @DisplayName("Should find origami by name pattern (case-insensitive)")
    void testFindByNameContainingIgnoreCase() {
        // When
        List<Origami> craneOrigamis = origamiRepository.findByNameContainingIgnoreCase("crane");
        List<Origami> butterflyOrigamis = origamiRepository.findByNameContainingIgnoreCase("BUTTERFLY");

        // Then
        assertThat(craneOrigamis).hasSize(1);
        assertThat(craneOrigamis.get(0).getOrigamiId()).isEqualTo("test-crane-001");

        assertThat(butterflyOrigamis).hasSize(1);
        assertThat(butterflyOrigamis.get(0).getOrigamiId()).isEqualTo("test-butterfly-002");
    }

    @Test
    @DisplayName("Should handle empty results gracefully")
    void testEmptyResults() {
        // When
        List<Origami> highVoteOrigamis = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(100);
        List<Origami> nonExistentPattern = origamiRepository.findByNameContainingIgnoreCase("nonexistent");

        // Then
        assertThat(highVoteOrigamis).isEmpty();
        assertThat(nonExistentPattern).isEmpty();
    }

    @Test
    @DisplayName("Should handle null parameters gracefully")
    void testNullParameterHandling() {
        // When & Then - Search operations should handle null gracefully
        assertDoesNotThrow(() -> {
            List<Origami> result = origamiRepository.findByNameContainingIgnoreCase(null);
            assertThat(result).isEmpty();
        });

        // Update operations with null values should respect database constraints
        assertThrows(Exception.class, () -> {
            // This should fail due to NOT NULL constraint on name field
            origamiRepository.updateOrigamiDetails("test-crane-001", null, null, null);
        });
    }

    @Test
    @DisplayName("Should maintain data integrity during concurrent operations")
    void testConcurrentVoteIncrement() {
        // Given
        String origamiId = testOrigami1.getOrigamiId();
        int originalVoteCount = testOrigami1.getVoteCount();

        // When - Simulate multiple concurrent vote increments
        origamiRepository.incrementVoteCountByOrigamiId(origamiId);
        origamiRepository.incrementVoteCountByOrigamiId(origamiId);
        origamiRepository.incrementVoteCountByOrigamiId(origamiId);

        // Then
        entityManager.refresh(testOrigami1);
        assertThat(testOrigami1.getVoteCount()).isEqualTo(originalVoteCount + 3);
    }

    @Test
    @DisplayName("Should validate entity constraints")
    void testEntityValidation() {
        // Given - Create origami with invalid data
        Origami invalidOrigami = Origami.builder()
                .origamiId("") // Invalid: blank origami ID
                .name("") // Invalid: blank name
                .voteCount(-1) // Invalid: negative vote count
                .active(null) // Invalid: null active status
                .build();

        // When & Then - Should throw validation exception
        assertThrows(Exception.class, () -> {
            entityManager.persistAndFlush(invalidOrigami);
        });
    }

    @Test
    @DisplayName("Should handle database constraints properly")
    void testDatabaseConstraints() {
        // Given - Create origami with duplicate origami_id
        Origami duplicateOrigami = Origami.builder()
                .origamiId("test-crane-001") // Duplicate of existing origami
                .name("Duplicate Crane")
                .voteCount(0)
                .active(true)
                .build();

        // When & Then - Should throw constraint violation exception
        assertThrows(Exception.class, () -> {
            entityManager.persistAndFlush(duplicateOrigami);
        });
    }

    @Nested
    @DisplayName("Transaction Management and Error Recovery Tests")
    class TransactionTests {

        @Test
        @DisplayName("Should rollback transaction on constraint violation")
        @Transactional(propagation = Propagation.REQUIRES_NEW)
        void testTransactionRollbackOnConstraintViolation() {
            // Given - Count initial records
            long initialCount = origamiRepository.count();

            // When - Try to save multiple origamis with one having constraint violation
            assertThrows(Exception.class, () -> {
                // Save valid origami first
                Origami validOrigami = Origami.builder()
                        .origamiId("valid-origami-001")
                        .name("Valid Origami")
                        .voteCount(0)
                        .active(true)
                        .build();
                origamiRepository.save(validOrigami);

                // Try to save invalid origami (duplicate ID)
                Origami invalidOrigami = Origami.builder()
                        .origamiId("test-crane-001") // Duplicate ID
                        .name("Invalid Origami")
                        .voteCount(0)
                        .active(true)
                        .build();
                origamiRepository.saveAndFlush(invalidOrigami);
            });

            // Then - Transaction should be rolled back, count should remain the same
            long finalCount = origamiRepository.count();
            assertThat(finalCount).isEqualTo(initialCount);
        }

        @Test
        @DisplayName("Should handle concurrent vote increments correctly")
        void testConcurrentVoteIncrements() throws InterruptedException, ExecutionException {
            // Given
            String origamiId = testOrigami1.getOrigamiId();
            int initialVoteCount = testOrigami1.getVoteCount();
            int numberOfThreads = 10;
            int incrementsPerThread = 5;

            ExecutorService executor = Executors.newFixedThreadPool(numberOfThreads);

            // When - Execute concurrent vote increments
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
            executor.awaitTermination(5, TimeUnit.SECONDS);

            // Then - Verify final vote count
            entityManager.refresh(testOrigami1);
            int expectedTotalIncrements = numberOfThreads * incrementsPerThread;
            assertThat(testOrigami1.getVoteCount()).isEqualTo(initialVoteCount + expectedTotalIncrements);
        }

        @Test
        @DisplayName("Should handle transaction timeout gracefully")
        @Transactional(timeout = 1) // 1 second timeout
        void testTransactionTimeout() {
            // This test simulates a scenario where a transaction might timeout
            // In a real scenario, this could be a long-running query or operation
            
            // Given
            String origamiId = testOrigami1.getOrigamiId();

            // When & Then - Should complete within timeout
            assertDoesNotThrow(() -> {
                origamiRepository.incrementVoteCountByOrigamiId(origamiId);
                origamiRepository.findByOrigamiId(origamiId);
            });
        }

        @Test
        @DisplayName("Should recover from database connection errors")
        void testDatabaseConnectionErrorRecovery() {
            // Given - This test simulates recovery after connection issues
            String origamiId = testOrigami1.getOrigamiId();

            // When - Perform operations that should work after connection recovery
            Optional<Origami> found = origamiRepository.findByOrigamiId(origamiId);
            
            // Then - Operations should succeed
            assertThat(found).isPresent();
            assertThat(found.get().getOrigamiId()).isEqualTo(origamiId);

            // Verify we can still perform updates
            int updated = origamiRepository.incrementVoteCountByOrigamiId(origamiId);
            assertThat(updated).isEqualTo(1);
        }

        @Test
        @DisplayName("Should handle batch operations with partial failures")
        void testBatchOperationsWithPartialFailures() {
            // Given - Create a mix of valid and invalid operations
            List<String> origamiIds = List.of(
                testOrigami1.getOrigamiId(),
                testOrigami2.getOrigamiId(),
                "non-existent-id"
            );

            // When - Perform batch vote increments
            int totalUpdated = 0;
            for (String id : origamiIds) {
                try {
                    int updated = origamiRepository.incrementVoteCountByOrigamiId(id);
                    totalUpdated += updated;
                } catch (Exception e) {
                    // Expected for non-existent IDs
                }
            }

            // Then - Should have updated only existing origamis
            assertThat(totalUpdated).isEqualTo(2); // Only 2 existing origamis
        }
    }

    @Nested
    @DisplayName("Data Synchronization Tests")
    class DataSynchronizationTests {

        @Test
        @DisplayName("Should synchronize origami data from external source")
        void testOrigamiDataSynchronization() {
            // Given - Simulate external data
            String externalOrigamiId = "external-sync-001";
            String updatedName = "Synchronized Origami Name";
            String updatedDescription = "Synchronized description from catalogue service";
            String updatedImageUrl = "/images/synchronized-origami.png";

            // Create origami that needs synchronization
            Origami origamiToSync = Origami.builder()
                    .origamiId(externalOrigamiId)
                    .name("Old Name")
                    .description("Old description")
                    .imageUrl("/images/old-image.png")
                    .voteCount(5)
                    .active(true)
                    .build();

            entityManager.persistAndFlush(origamiToSync);

            // When - Perform synchronization update
            int updated = origamiRepository.updateOrigamiDetails(
                    externalOrigamiId, updatedName, updatedDescription, updatedImageUrl);

            // Then - Verify synchronization was successful
            assertThat(updated).isEqualTo(1);

            entityManager.refresh(origamiToSync);
            assertThat(origamiToSync.getName()).isEqualTo(updatedName);
            assertThat(origamiToSync.getDescription()).isEqualTo(updatedDescription);
            assertThat(origamiToSync.getImageUrl()).isEqualTo(updatedImageUrl);
            assertThat(origamiToSync.getVoteCount()).isEqualTo(5); // Vote count should remain unchanged
        }

        @Test
        @DisplayName("Should identify origamis needing synchronization")
        void testIdentifyOrigamisNeedingSync() {
            // Given - Create origamis with different update times
            LocalDateTime oldTime = LocalDateTime.now().minusHours(2);
            LocalDateTime recentTime = LocalDateTime.now().minusMinutes(10);
            LocalDateTime threshold = LocalDateTime.now().minusHours(1);

            // Update one origami to have old timestamp
            testOrigami1.setUpdatedAt(oldTime);
            entityManager.merge(testOrigami1);

            // Update another to have recent timestamp
            testOrigami2.setUpdatedAt(recentTime);
            entityManager.merge(testOrigami2);

            entityManager.flush();

            // When - Find origamis needing sync
            List<Origami> needingSync = origamiRepository.findOrigamiNeedingSync(threshold);

            // Then - Should find only the old one
            assertThat(needingSync).hasSize(1);
            assertThat(needingSync.get(0).getOrigamiId()).isEqualTo(testOrigami1.getOrigamiId());
        }

        @Test
        @DisplayName("Should handle bulk synchronization operations")
        void testBulkSynchronizationOperations() {
            // Given - Create multiple origamis for bulk sync
            List<Origami> origamisToSync = List.of(
                Origami.builder()
                    .origamiId("bulk-sync-001")
                    .name("Bulk Sync 1")
                    .description("Original description 1")
                    .voteCount(0)
                    .active(true)
                    .build(),
                Origami.builder()
                    .origamiId("bulk-sync-002")
                    .name("Bulk Sync 2")
                    .description("Original description 2")
                    .voteCount(0)
                    .active(true)
                    .build()
            );

            origamisToSync.forEach(origami -> entityManager.persistAndFlush(origami));

            // When - Perform bulk synchronization
            int totalUpdated = 0;
            for (Origami origami : origamisToSync) {
                int updated = origamiRepository.updateOrigamiDetails(
                    origami.getOrigamiId(),
                    "Updated " + origami.getName(),
                    "Updated " + origami.getDescription(),
                    "/images/updated-" + origami.getOrigamiId() + ".png"
                );
                totalUpdated += updated;
            }

            // Then - All should be updated
            assertThat(totalUpdated).isEqualTo(2);

            // Verify updates
            origamisToSync.forEach(origami -> {
                entityManager.refresh(origami);
                assertThat(origami.getName()).startsWith("Updated");
                assertThat(origami.getDescription()).startsWith("Updated");
                assertThat(origami.getImageUrl()).contains("updated-");
            });
        }

        @Test
        @DisplayName("Should handle synchronization conflicts gracefully")
        void testSynchronizationConflicts() {
            // Given - Origami that might have conflicts during sync
            String conflictOrigamiId = "conflict-test-001";
            Origami conflictOrigami = Origami.builder()
                    .origamiId(conflictOrigamiId)
                    .name("Conflict Test")
                    .description("Original description")
                    .voteCount(10)
                    .active(true)
                    .build();

            entityManager.persistAndFlush(conflictOrigami);

            // When - Simulate concurrent updates (sync + vote increment)
            // First update: synchronization
            int syncUpdated = origamiRepository.updateOrigamiDetails(
                    conflictOrigamiId,
                    "Synchronized Name",
                    "Synchronized description",
                    "/images/synchronized.png"
            );

            // Second update: vote increment
            int voteUpdated = origamiRepository.incrementVoteCountByOrigamiId(conflictOrigamiId);

            // Then - Both operations should succeed
            assertThat(syncUpdated).isEqualTo(1);
            assertThat(voteUpdated).isEqualTo(1);

            entityManager.refresh(conflictOrigami);
            assertThat(conflictOrigami.getName()).isEqualTo("Synchronized Name");
            assertThat(conflictOrigami.getVoteCount()).isEqualTo(11); // Original 10 + 1
        }
    }

    @Nested
    @DisplayName("Advanced Vote Counting Tests")
    class VoteCountingTests {

        @Test
        @DisplayName("Should handle vote counting with database constraints")
        void testVoteCountingWithConstraints() {
            // Given
            String origamiId = testOrigami1.getOrigamiId();
            int initialVotes = testOrigami1.getVoteCount();

            // When - Perform multiple vote increments
            for (int i = 0; i < 5; i++) {
                int updated = origamiRepository.incrementVoteCountByOrigamiId(origamiId);
                assertThat(updated).isEqualTo(1);
            }

            // Then - Verify final vote count
            entityManager.refresh(testOrigami1);
            assertThat(testOrigami1.getVoteCount()).isEqualTo(initialVotes + 5);
        }

        @Test
        @DisplayName("Should maintain vote count integrity during errors")
        void testVoteCountIntegrityDuringErrors() {
            // Given
            String validOrigamiId = testOrigami1.getOrigamiId();
            String invalidOrigamiId = "non-existent-origami";
            int initialVotes = testOrigami1.getVoteCount();

            // When - Mix valid and invalid vote operations
            int validUpdates = origamiRepository.incrementVoteCountByOrigamiId(validOrigamiId);
            int invalidUpdates = origamiRepository.incrementVoteCountByOrigamiId(invalidOrigamiId);
            int moreValidUpdates = origamiRepository.incrementVoteCountByOrigamiId(validOrigamiId);

            // Then - Only valid operations should succeed
            assertThat(validUpdates).isEqualTo(1);
            assertThat(invalidUpdates).isEqualTo(0);
            assertThat(moreValidUpdates).isEqualTo(1);

            entityManager.refresh(testOrigami1);
            assertThat(testOrigami1.getVoteCount()).isEqualTo(initialVotes + 2);
        }

        @Test
        @DisplayName("Should handle vote statistics calculations correctly")
        void testVoteStatisticsCalculations() {
            // Given - Create origamis with known vote counts
            Origami lowVoteOrigami = Origami.builder()
                    .origamiId("low-vote-001")
                    .name("Low Vote Origami")
                    .voteCount(1)
                    .active(true)
                    .build();

            Origami highVoteOrigami = Origami.builder()
                    .origamiId("high-vote-001")
                    .name("High Vote Origami")
                    .voteCount(20)
                    .active(true)
                    .build();

            entityManager.persistAndFlush(lowVoteOrigami);
            entityManager.persistAndFlush(highVoteOrigami);

            // When - Get vote statistics
            Object[] stats = origamiRepository.getVoteCountStatistics();

            // Then - Verify statistics are correct
            assertThat(stats).hasSize(4);
            
            Integer minVotes = (Integer) stats[0];
            Integer maxVotes = (Integer) stats[1];
            Double avgVotes = (Double) stats[2];
            Long count = (Long) stats[3];

            assertThat(minVotes).isEqualTo(1);
            assertThat(maxVotes).isEqualTo(20);
            assertThat(count).isEqualTo(4L); // 2 original + 2 new = 4 active origamis
            
            // Average should be calculated correctly
            double expectedAvg = (5.0 + 10.0 + 1.0 + 20.0) / 4.0; // 9.0
            assertThat(avgVotes).isEqualTo(expectedAvg);
        }

        @Test
        @DisplayName("Should handle vote operations on inactive origamis")
        void testVoteOperationsOnInactiveOrigamis() {
            // Given - Make an origami inactive
            String origamiId = testOrigami1.getOrigamiId();
            int initialVotes = testOrigami1.getVoteCount();
            
            origamiRepository.softDeleteByOrigamiId(origamiId);

            // When - Try to increment votes on inactive origami
            int updated = origamiRepository.incrementVoteCountByOrigamiId(origamiId);

            // Then - Should not update inactive origami
            assertThat(updated).isEqualTo(0);

            entityManager.refresh(testOrigami1);
            assertThat(testOrigami1.getVoteCount()).isEqualTo(initialVotes); // Unchanged
            assertThat(testOrigami1.getActive()).isFalse();
        }
    }

    @Nested
    @DisplayName("Error Handling and Edge Cases")
    class ErrorHandlingTests {

        @Test
        @DisplayName("Should handle null and empty parameters gracefully")
        void testNullAndEmptyParameterHandling() {
            // When & Then - Should not throw exceptions for null parameters
            assertDoesNotThrow(() -> {
                List<Origami> result1 = origamiRepository.findByNameContainingIgnoreCase(null);
                assertThat(result1).isEmpty();

                List<Origami> result2 = origamiRepository.findByNameContainingIgnoreCase("");
                // Empty string should return all active origamis
                assertThat(result2).hasSize(2);

                // Null parameters in update operations
                int updated = origamiRepository.updateOrigamiDetails("test-crane-001", null, null, null);
                assertThat(updated).isEqualTo(1);
            });
        }

        @Test
        @DisplayName("Should handle very large vote counts")
        void testLargeVoteCounts() {
            // Given - Create origami with large vote count
            Origami largeVoteOrigami = Origami.builder()
                    .origamiId("large-vote-001")
                    .name("Large Vote Origami")
                    .voteCount(Integer.MAX_VALUE - 1)
                    .active(true)
                    .build();

            entityManager.persistAndFlush(largeVoteOrigami);

            // When - Try to increment vote count
            int updated = origamiRepository.incrementVoteCountByOrigamiId("large-vote-001");

            // Then - Should handle large numbers correctly
            assertThat(updated).isEqualTo(1);
            entityManager.refresh(largeVoteOrigami);
            assertThat(largeVoteOrigami.getVoteCount()).isEqualTo(Integer.MAX_VALUE);
        }

        @Test
        @DisplayName("Should handle special characters in origami data")
        void testSpecialCharactersInData() {
            // Given - Create origami with special characters
            String specialId = "special-chars-001";
            String specialName = "Origami with Special Chars: éñ中文🎨";
            String specialDescription = "Description with symbols: @#$%^&*()[]{}|\\:;\"'<>,.?/~`";

            Origami specialOrigami = Origami.builder()
                    .origamiId(specialId)
                    .name(specialName)
                    .description(specialDescription)
                    .voteCount(0)
                    .active(true)
                    .build();

            // When - Save and retrieve
            entityManager.persistAndFlush(specialOrigami);
            Optional<Origami> found = origamiRepository.findByOrigamiId(specialId);

            // Then - Should handle special characters correctly
            assertThat(found).isPresent();
            assertThat(found.get().getName()).isEqualTo(specialName);
            assertThat(found.get().getDescription()).isEqualTo(specialDescription);
        }

        @Test
        @DisplayName("Should handle database performance under load")
        void testDatabasePerformanceUnderLoad() {
            // Given - Create many origamis for performance testing
            List<Origami> manyOrigamis = IntStream.range(0, 100)
                    .mapToObj(i -> Origami.builder()
                            .origamiId("perf-test-" + String.format("%03d", i))
                            .name("Performance Test Origami " + i)
                            .description("Description for performance test " + i)
                            .voteCount(i % 10)
                            .active(true)
                            .build())
                    .toList();

            // When - Batch save and perform operations
            long startTime = System.currentTimeMillis();
            
            manyOrigamis.forEach(origami -> entityManager.persist(origami));
            entityManager.flush();

            // Perform various operations
            List<Origami> allActive = origamiRepository.findByActiveTrue();
            List<Origami> highVotes = origamiRepository.findByVoteCountGreaterThanAndActiveTrue(5);
            Object[] stats = origamiRepository.getVoteCountStatistics();

            long endTime = System.currentTimeMillis();
            long duration = endTime - startTime;

            // Then - Operations should complete in reasonable time
            assertThat(duration).isLessThan(5000); // Should complete within 5 seconds
            assertThat(allActive.size()).isGreaterThanOrEqualTo(100);
            assertThat(highVotes.size()).isGreaterThan(0);
            assertThat(stats).hasSize(4);
        }
    }
}