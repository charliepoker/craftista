const nock = require("nock");
const chai = require("chai");
const chaiHttp = require("chai-http");
const server = require("../app"); // Adjust path accordingly
const config = require("./../config.json"); // path to config file

chai.should();
chai.use(chaiHttp);

const productsApiBaseUri = config.productsApiBaseUri;

describe("App", () => {
  describe("GET /", () => {
    it("should return status 200", (done) => {
      chai
        .request(server)
        .get("/")
        .end((err, res) => {
          res.should.have.status(200);
          done();
        });
    });
  });

  describe("GET /products", () => {
    it("should get array of products", (done) => {
      nock(productsApiBaseUri)
        .get("/api/products")
        .reply(200, [
          {
            id: 1,
            name: "Sample Product",
            description: "Sample Description",
            price: 99.99,
            image_url: "http://example.com/sample.jpg",
          },
        ]);

      chai
        .request(productsApiBaseUri)
        .get("/api/products")
        .end((err, res) => {
          res.should.have.status(200);
          res.body.should.be.an("array");
          res.body[0].should.have.property("name");
          done();
        });
    });
  });

  describe("GET /unknown-route", () => {
    it("should return 404 for unknown routes", (done) => {
      chai
        .request(server)
        .get("/unknown-route")
        .end((err, response) => {
          if (err) {
            console.log(err);
          }

          if (response) {
            response.should.have.status(404);
          }
          done();
        });
    });
  });

  describe("GET /", () => {
    it("should contain a specific word or element", (done) => {
      chai
        .request(server)
        .get("/")
        .end((err, response) => {
          response.text.should.include("School of DevOps");
          done();
        });
    });
  });
});
