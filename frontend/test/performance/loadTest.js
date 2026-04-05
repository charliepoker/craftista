const chai = require("chai");
const chaiHttp = require("chai-http");
const nock = require("nock");
const server = require("../../app");
const config = require("../../config.json");
const expect = chai.expect;

chai.use(chaiHttp);

/**
 * Performance tests for frontend service under load.
 *
 * These tests validate that the frontend can handle expected load patterns
 * and identify performance bottlenecks in API aggregation and response times.
 */
describe("Frontend Performance Tests", function () {
  // Increase timeout for performance tests
  this.timeout(60000);

  const productsApiBaseUri = config.productsApiBaseUri;
  const votingApiBaseUri = config.votingApiBaseUri || "http://localhost:8080";
  const recommendationApiBaseUri =
    config.recommendationApiBaseUri || "http://localhost:9090";

  beforeEach(() => {
    // Clear any existing nock interceptors
    nock.cleanAll();
  });

  afterEach(() => {
    // Clean up nock interceptors
    nock.cleanAll();
  });

  describe("High Volume Request Handling", () => {
    it("should handle high volume of concurrent homepage requests", async () => {
      // Mock API responses for all services
      const mockProducts = Array.from({ length: 20 }, (_, i) => ({
        id: i + 1,
        name: `Performance Test Product ${i + 1}`,
        description: `Description for performance test product ${i + 1}`,
        price: 10.99 + i,
        image_url: `/images/perf-product-${i + 1}.jpg`,
      }));

      const mockVotingData = Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        origami_id: `perf-origami-${i + 1}`,
        name: `Performance Origami ${i + 1}`,
        vote_count: Math.floor(Math.random() * 100),
        active: true,
      }));

      const mockRecommendations = Array.from({ length: 5 }, (_, i) => ({
        id: `rec-${i + 1}`,
        name: `Recommended Item ${i + 1}`,
        score: 9.0 - i * 0.2,
        reason: "Popular choice",
      }));

      // Setup persistent mocks for the duration of the test
      const productsScope = nock(productsApiBaseUri)
        .persist()
        .get("/api/products")
        .reply(200, mockProducts);

      const votingScope = nock(votingApiBaseUri)
        .persist()
        .get("/api/origami")
        .reply(200, mockVotingData);

      const recommendationScope = nock(recommendationApiBaseUri)
        .persist()
        .get("/api/recommendations")
        .reply(200, mockRecommendations);

      // Performance test: concurrent requests
      const concurrentRequests = 100;
      const startTime = Date.now();

      const requests = Array.from({ length: concurrentRequests }, () =>
        chai
          .request(server)
          .get("/")
          .then((res) => {
            expect(res).to.have.status(200);
            return res;
          })
      );

      const responses = await Promise.all(requests);
      const endTime = Date.now();
      const duration = endTime - startTime;
      const requestsPerSecond = (concurrentRequests / duration) * 1000;

      // Performance assertions
      expect(responses).to.have.length(concurrentRequests);
      expect(duration).to.be.lessThan(10000); // Should complete within 10 seconds
      expect(requestsPerSecond).to.be.greaterThan(10); // Should handle > 10 requests/second

      // Clean up persistent mocks
      productsScope.persist(false);
      votingScope.persist(false);
      recommendationScope.persist(false);
    });

    it("should handle API timeout scenarios gracefully", async () => {
      // Mock slow API responses
      const slowProductsScope = nock(productsApiBaseUri)
        .get("/api/products")
        .delay(2000) // 2 second delay
        .reply(200, []);

      const fastVotingScope = nock(votingApiBaseUri)
        .get("/api/origami")
        .reply(200, []);

      const timeoutRecommendationScope = nock(recommendationApiBaseUri)
        .get("/api/recommendations")
        .delay(5000) // 5 second delay
        .reply(200, []);

      const startTime = Date.now();

      const response = await chai.request(server).get("/").timeout(8000); // 8 second timeout

      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should still respond even with slow APIs
      expect(response).to.have.status(200);
      expect(duration).to.be.lessThan(8000); // Should not exceed timeout
    });
  });

  describe("API Aggregation Performance", () => {
    it("should efficiently aggregate data from multiple services", async () => {
      // Mock responses from all services
      const largeProductSet = Array.from({ length: 100 }, (_, i) => ({
        id: i + 1,
        name: `Product ${i + 1}`,
        description: `Description ${i + 1}`,
        price: 5.99 + i,
        image_url: `/images/product-${i + 1}.jpg`,
      }));

      nock(productsApiBaseUri).get("/api/products").reply(200, largeProductSet);

      nock(votingApiBaseUri)
        .get("/api/origami")
        .reply(
          200,
          Array.from({ length: 50 }, (_, i) => ({
            id: i + 1,
            name: `Origami ${i + 1}`,
            vote_count: i * 2,
            active: true,
          }))
        );

      nock(recommendationApiBaseUri)
        .get("/api/recommendations")
        .reply(
          200,
          Array.from({ length: 10 }, (_, i) => ({
            id: `rec-${i + 1}`,
            name: `Recommendation ${i + 1}`,
            score: 8.5 - i * 0.1,
          }))
        );

      const startTime = Date.now();

      const response = await chai.request(server).get("/");

      const endTime = Date.now();
      const aggregationTime = endTime - startTime;

      // Performance assertions for data aggregation
      expect(response).to.have.status(200);
      expect(aggregationTime).to.be.lessThan(3000); // Should aggregate within 3 seconds
      expect(response.text).to.include("School of DevOps"); // Verify content is rendered
    });

    it("should handle partial API failures gracefully", async () => {
      // Mock mixed success/failure scenarios
      nock(productsApiBaseUri)
        .get("/api/products")
        .reply(200, [
          {
            id: 1,
            name: "Working Product",
            description: "This API is working",
            price: 19.99,
          },
        ]);

      nock(votingApiBaseUri)
        .get("/api/origami")
        .reply(500, { error: "Internal Server Error" });

      nock(recommendationApiBaseUri)
        .get("/api/recommendations")
        .reply(200, [
          {
            id: "rec-1",
            name: "Working Recommendation",
            score: 9.0,
          },
        ]);

      const startTime = Date.now();

      const response = await chai.request(server).get("/");

      const endTime = Date.now();
      const responseTime = endTime - startTime;

      // Should still respond with partial data
      expect(response).to.have.status(200);
      expect(responseTime).to.be.lessThan(5000); // Should handle failures quickly
    });
  });

  describe("Memory Usage Under Load", () => {
    it("should maintain stable memory usage during sustained load", async () => {
      // Mock lightweight responses
      nock(productsApiBaseUri)
        .persist()
        .get("/api/products")
        .reply(200, [{ id: 1, name: "Test Product", price: 9.99 }]);

      nock(votingApiBaseUri)
        .persist()
        .get("/api/origami")
        .reply(200, [{ id: 1, name: "Test Origami", vote_count: 5 }]);

      nock(recommendationApiBaseUri)
        .persist()
        .get("/api/recommendations")
        .reply(200, [{ id: "rec-1", name: "Test Rec", score: 8.0 }]);

      // Get initial memory usage
      const initialMemory = process.memoryUsage();

      // Sustained load test
      const batches = 20;
      const requestsPerBatch = 25;

      for (let batch = 0; batch < batches; batch++) {
        const batchRequests = Array.from({ length: requestsPerBatch }, () =>
          chai
            .request(server)
            .get("/")
            .then((res) => expect(res).to.have.status(200))
        );

        await Promise.all(batchRequests);

        // Force garbage collection periodically
        if (batch % 5 === 0 && global.gc) {
          global.gc();
        }
      }

      // Check final memory usage
      const finalMemory = process.memoryUsage();
      const memoryIncrease = finalMemory.heapUsed - initialMemory.heapUsed;

      // Memory usage should not increase dramatically
      expect(memoryIncrease).to.be.lessThan(50 * 1024 * 1024); // Less than 50MB increase
    });
  });

  describe("Response Time Consistency", () => {
    it("should maintain consistent response times under varying load", async () => {
      // Mock consistent API responses
      nock(productsApiBaseUri)
        .persist()
        .get("/api/products")
        .reply(200, [{ id: 1, name: "Consistent Product", price: 15.99 }]);

      nock(votingApiBaseUri)
        .persist()
        .get("/api/origami")
        .reply(200, [{ id: 1, name: "Consistent Origami", vote_count: 10 }]);

      nock(recommendationApiBaseUri)
        .persist()
        .get("/api/recommendations")
        .reply(200, [{ id: "rec-1", name: "Consistent Rec", score: 7.5 }]);

      const loadLevels = [1, 5, 10, 20];
      const responseTimes = {};

      for (const load of loadLevels) {
        const times = [];

        for (let i = 0; i < 10; i++) {
          const requests = Array.from({ length: load }, async () => {
            const startTime = Date.now();
            const response = await chai.request(server).get("/");
            const endTime = Date.now();

            expect(response).to.have.status(200);
            return endTime - startTime;
          });

          const batchTimes = await Promise.all(requests);
          times.push(...batchTimes);
        }

        // Calculate statistics
        times.sort((a, b) => a - b);
        const median = times[Math.floor(times.length / 2)];
        const p95 = times[Math.floor(times.length * 0.95)];

        responseTimes[load] = { median, p95, times };

        // Response time assertions
        expect(median).to.be.lessThan(1000); // Median < 1 second
        expect(p95).to.be.lessThan(3000); // 95th percentile < 3 seconds
      }

      // Verify response times don't degrade significantly with load
      const baselineMedian = responseTimes[1].median;
      const highLoadMedian = responseTimes[20].median;
      const degradationRatio = highLoadMedian / baselineMedian;

      expect(degradationRatio).to.be.lessThan(3); // Should not degrade more than 3x
    });
  });

  describe("Error Rate Under Load", () => {
    it("should maintain low error rates under high concurrent load", async () => {
      // Mock mostly successful responses with occasional failures
      let requestCount = 0;

      nock(productsApiBaseUri)
        .persist()
        .get("/api/products")
        .reply(() => {
          requestCount++;
          // 5% failure rate
          if (requestCount % 20 === 0) {
            return [500, { error: "Simulated failure" }];
          }
          return [200, [{ id: 1, name: "Load Test Product", price: 12.99 }]];
        });

      nock(votingApiBaseUri)
        .persist()
        .get("/api/origami")
        .reply(200, [{ id: 1, name: "Load Test Origami", vote_count: 15 }]);

      nock(recommendationApiBaseUri)
        .persist()
        .get("/api/recommendations")
        .reply(200, [{ id: "rec-1", name: "Load Test Rec", score: 8.2 }]);

      // High load test
      const totalRequests = 200;
      let successCount = 0;
      let errorCount = 0;

      const requests = Array.from({ length: totalRequests }, async () => {
        try {
          const response = await chai.request(server).get("/");
          if (response.status === 200) {
            successCount++;
          } else {
            errorCount++;
          }
          return response;
        } catch (error) {
          errorCount++;
          throw error;
        }
      });

      await Promise.allSettled(requests);

      const errorRate = (errorCount / totalRequests) * 100;
      const successRate = (successCount / totalRequests) * 100;

      // Error rate assertions
      expect(successRate).to.be.greaterThan(90); // > 90% success rate
      expect(errorRate).to.be.lessThan(10); // < 10% error rate
    });
  });

  describe("Scalability Metrics", () => {
    it("should demonstrate linear scalability up to reasonable limits", async () => {
      // Mock fast, consistent API responses
      nock(productsApiBaseUri)
        .persist()
        .get("/api/products")
        .reply(200, [{ id: 1, name: "Scalability Product", price: 8.99 }]);

      nock(votingApiBaseUri)
        .persist()
        .get("/api/origami")
        .reply(200, [{ id: 1, name: "Scalability Origami", vote_count: 20 }]);

      nock(recommendationApiBaseUri)
        .persist()
        .get("/api/recommendations")
        .reply(200, [{ id: "rec-1", name: "Scalability Rec", score: 9.1 }]);

      const concurrencyLevels = [1, 5, 10, 25, 50];
      const requestsPerLevel = 100;
      const throughputResults = {};

      for (const concurrency of concurrencyLevels) {
        const startTime = Date.now();

        const batches = Math.ceil(requestsPerLevel / concurrency);

        for (let batch = 0; batch < batches; batch++) {
          const batchSize = Math.min(
            concurrency,
            requestsPerLevel - batch * concurrency
          );

          const batchRequests = Array.from({ length: batchSize }, () =>
            chai
              .request(server)
              .get("/")
              .then((res) => expect(res).to.have.status(200))
          );

          await Promise.all(batchRequests);
        }

        const endTime = Date.now();
        const duration = (endTime - startTime) / 1000; // Convert to seconds
        const throughput = requestsPerLevel / duration;

        throughputResults[concurrency] = throughput;

        // Basic throughput assertion
        expect(throughput).to.be.greaterThan(5); // Should handle > 5 requests/second
      }

      // Verify scaling characteristics
      const singleThreadThroughput = throughputResults[1];
      const moderateConcurrencyThroughput = throughputResults[10];

      // Should see some improvement with moderate concurrency
      expect(moderateConcurrencyThroughput).to.be.greaterThan(
        singleThreadThroughput * 0.8
      );
    });
  });
});
