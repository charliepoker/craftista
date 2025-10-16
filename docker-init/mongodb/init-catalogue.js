// MongoDB initialization script for Catalogue database
// This script creates the catalogue database, user, and initial collections

// Switch to the catalogue database
db = db.getSiblingDB("catalogue");

// Create a user for the catalogue service
db.createUser({
  user: "catalogue_user",
  pwd: "catalogue_pass",
  roles: [
    {
      role: "readWrite",
      db: "catalogue",
    },
  ],
});

// Create the products collection with validation schema
db.createCollection("products", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "active", "created_at", "updated_at"],
      properties: {
        name: {
          bsonType: "string",
          minLength: 1,
          maxLength: 255,
          description:
            "Product name is required and must be a string between 1-255 characters",
        },
        description: {
          bsonType: ["string", "null"],
          maxLength: 2000,
          description:
            "Product description must be a string with max 2000 characters",
        },
        image_url: {
          bsonType: ["string", "null"],
          description: "Image URL must be a string",
        },
        price: {
          bsonType: ["number", "null"],
          minimum: 0,
          description: "Price must be a non-negative number",
        },
        category: {
          bsonType: ["string", "null"],
          maxLength: 100,
          description: "Category must be a string with max 100 characters",
        },
        tags: {
          bsonType: "array",
          items: {
            bsonType: "string",
          },
          description: "Tags must be an array of strings",
        },
        attributes: {
          bsonType: "object",
          description: "Attributes must be an object",
        },
        active: {
          bsonType: "bool",
          description: "Active status is required and must be a boolean",
        },
        featured: {
          bsonType: "bool",
          description: "Featured status must be a boolean",
        },
        inventory_count: {
          bsonType: ["int", "null"],
          minimum: 0,
          description: "Inventory count must be a non-negative integer",
        },
        created_at: {
          bsonType: "date",
          description: "Created timestamp is required",
        },
        updated_at: {
          bsonType: "date",
          description: "Updated timestamp is required",
        },
      },
    },
  },
});

// Create indexes for performance optimization
db.products.createIndex({ name: "text", description: "text" }); // Text search
db.products.createIndex({ category: 1, active: 1 }); // Category filtering
db.products.createIndex({ tags: 1 }); // Tag-based queries
db.products.createIndex({ featured: 1, active: 1 }); // Featured products
db.products.createIndex({ created_at: -1 }); // Recent products
db.products.createIndex({ price: 1, active: 1 }); // Price filtering
db.products.createIndex({ inventory_count: 1, active: 1 }); // Stock filtering

// Insert initial product data
db.products.insertMany([
  {
    name: "Origami Crane",
    description:
      "Behold the delicate elegance of this Origami Crane, rendered in soft pastel hues that lend it an ethereal charm. The graceful arch of its wings and the poised curvature of its neck evoke a sense of serenity and balance. Each meticulously folded crease tells a story of patience and precision, capturing the essence of the traditional art of paper folding. The gentle gradient of its pink hue enhances its beauty, reflecting the transient glow of a setting sun. This paper masterpiece serves as a poignant symbol of peace, hope, and the intricate dance of art and nature.",
    image_url: "/static/images/origami/001-origami.png",
    price: 15.99,
    category: "origami",
    tags: ["paper", "craft", "decoration", "crane", "bird"],
    attributes: {
      difficulty: "intermediate",
      material: "paper",
      color: "pink",
      size: "medium",
    },
    active: true,
    featured: true,
    inventory_count: 50,
    created_at: new Date(),
    updated_at: new Date(),
  },
  {
    name: "Origami Frog",
    description:
      "Dive into the enchanting realm of the Origami Frog, a captivating representation of the amphibious wonders that inhabit our ponds and wetlands. This artful creation, with its bulging eyes and poised, springy legs, encapsulates the playful essence and sprightly demeanor of its real-life counterpart. Crafted with meticulous precision, each fold and crease brings to life the frog's distinctive features, from its wide mouth to its textured back. Its poised stance, as if ready to leap into the next adventure, invites onlookers into a world where nature's simple joys come alive through the magic of paper folding. The Origami Frog stands not just as a testament to the art of origami, but also as a delightful ode to the vibrant and lively spirit of these charming aquatic creatures.",
    image_url: "/static/images/origami/012-origami-8.png",
    price: 12.99,
    category: "origami",
    tags: ["paper", "craft", "decoration", "frog", "amphibian"],
    attributes: {
      difficulty: "beginner",
      material: "paper",
      color: "green",
      size: "small",
    },
    active: true,
    featured: false,
    inventory_count: 75,
    created_at: new Date(),
    updated_at: new Date(),
  },
  {
    name: "Origami Kangaroo",
    description:
      "Step into the rugged landscapes of the Australian outback with our Origami Kangaroo, a masterful depiction of one of the continent's most iconic marsupials. This paper creation, with its powerful hind legs and distinctive pouch, captures the unique essence and agile grace of the kangaroo. Each fold and contour meticulously represents its muscular build, upright posture, and the gentle curve of its tail, used for balance during those impressive leaps. The attentive gaze and erect ears portray an ever-alert nature, characteristic of these fascinating creatures. Beyond its aesthetic allure, the Origami Kangaroo is also a symbol of strength, adaptability, and the boundless wonders of the natural world, all wrapped into a single, intricate piece of art.",
    image_url: "/static/images/origami/010-origami-6.png",
    price: 18.99,
    category: "origami",
    tags: [
      "paper",
      "craft",
      "decoration",
      "kangaroo",
      "marsupial",
      "australia",
    ],
    attributes: {
      difficulty: "advanced",
      material: "paper",
      color: "brown",
      size: "large",
    },
    active: true,
    featured: true,
    inventory_count: 30,
    created_at: new Date(),
    updated_at: new Date(),
  },
  {
    name: "Origami Camel",
    description:
      "Journey into the sun-kissed dunes of the desert with our Origami Camel, a magnificent portrayal of the enduring giants that gracefully navigate the arid terrains. This artful masterpiece, with its humped back and long, graceful neck, perfectly encapsulates the camel's resilience and elegance. Each meticulous fold and crease gives life to its broad feet, adapted for sandy travels, and the gentle curve of its distinctive humps, which are nature's solution for long journeys without water. The poised stance and serene expression evoke images of golden horizons and the age-old tales of caravans that traverse vast landscapes under starry skies. The Origami Camel stands as a tribute to the majesty of these desert wanderers.",
    image_url: "/static/images/origami/021-camel.png",
    price: 16.99,
    category: "origami",
    tags: ["paper", "craft", "decoration", "camel", "desert", "animal"],
    attributes: {
      difficulty: "intermediate",
      material: "paper",
      color: "tan",
      size: "medium",
    },
    active: true,
    featured: false,
    inventory_count: 40,
    created_at: new Date(),
    updated_at: new Date(),
  },
  {
    name: "Origami Butterfly",
    description:
      "Witness the ephemeral beauty of our Origami Butterfly, a delicate creation symbolizing transformation and ethereal beauty. With wings that seem to flutter with an unspoken elegance, this piece allures eyes with its intricate patterns and gentle symmetries. Each fold carries with it a tale of metamorphosis, inviting you to embark upon a journey through blooming fields where these paper wonders flutter, leaving a trail of enchanted admirers in their gentle wake.",
    image_url: "/static/images/origami/017-origami-9.png",
    price: 14.99,
    category: "origami",
    tags: [
      "paper",
      "craft",
      "decoration",
      "butterfly",
      "insect",
      "transformation",
    ],
    attributes: {
      difficulty: "intermediate",
      material: "paper",
      color: "multicolor",
      size: "small",
    },
    active: true,
    featured: true,
    inventory_count: 60,
    created_at: new Date(),
    updated_at: new Date(),
  },
]);

print(
  "Catalogue database initialized successfully with " +
    db.products.countDocuments({}) +
    " products"
);
