let votingServiceAvailable = false; // global variable to store voting service status
let currentItems = 6; // global variable for current number of items to display
let allProducts = []; // global variable to store products for re-rendering

// Function to load and refresh product data
async function loadProducts() {
  try {
    const response = await fetch('/api/products');
    if (!response.ok) {
      throw new Error('Network response was not ok' + response.statusText);
    }
    const data = await response.json();
    allProducts = data; // Update global products array
    // Re-render products with current display count
    renderProducts(data.slice(0, currentItems), votingServiceAvailable);
  } catch (error) {
    console.error('Error loading products:', error);
  }
}

document.addEventListener('DOMContentLoaded', async function () {
  await checkVotingServiceStatus();
  //setInterval(checkVotingServiceStatus, 30000);  // checks voting service status every 30 se

  fetch('/api/products')
    .then((response) => {
      if (!response.ok) {
        throw new Error('Network response was not ok' + response.statusText);
      }
      return response.json();
    })
    .then((data) => {
      allProducts = data; // Store products for re-rendering
      // Render initial batch of products
      renderProducts(data.slice(0, currentItems), votingServiceAvailable);

      // Remove loading message
      document.getElementById('loading-message').style.display = 'none';

      // Set up infinite scroll
      window.addEventListener('scroll', function () {
        if (
          window.scrollY + window.innerHeight >=
          document.documentElement.scrollHeight
        ) {
          currentItems += 6; // add 6 more items each time
          renderProducts(allProducts.slice(0, currentItems), votingServiceAvailable);
        }
      });
    })
    .catch((error) => {
      console.error('There has been a problem with your fetch operation:', error);
    });

  document.addEventListener('click', function (event) {
    if (event.target.classList.contains('read-more')) {
      event.preventDefault();

      const descId = event.target.getAttribute('data-desc-id');
      const fullDescId = `full-${descId}`;

      document.getElementById(descId).classList.toggle('hidden');
      document.getElementById(fullDescId).classList.toggle('hidden');
    }
  });

  // Fetch and display service status
  fetchServiceStatus();

  // Fetch and display daily origami
  fetchDailyOrigami();

  checkRecommendationStatus();

  // Check status at regular intervals
  // setInterval(checkRecommendationStatus, 5000);
  // setInterval(fetchServiceStatus, 5000);
});

function renderProducts(products, canVote) {
  // Logic to display products on the page
  const productContainer = document.getElementById('products');
  productContainer.innerHTML = ''; // clear the existing items before appending
  products.forEach((product) => {
    const voteButtonHtml = canVote
      ? `<button onclick="submitVote(${product.id})">Vote 👍</button>`
      : '';
    const shortDescription = shortenDescription(product.description);

    const productElement = document.createElement('div');
    productElement.className = 'product';
    productElement.innerHTML = `
      <h3>${product.name}</h3>
      <img src="${product.image_url}" alt="${product.name}" />
      <p id="votes-${product.id}">Votes: Loading...</p>
      ${voteButtonHtml}
      <p class="description" id="desc-${product.id}">${shortDescription}</p>
      <a href="#" class="read-more" data-desc-id="desc-${product.id}">Read More</a>
      <p class="full-description hidden" id="full-desc-${product.id}">${product.description}</p>
    `;
    productContainer.appendChild(productElement);
    // Fetch votes for this origami
    fetchVotesForOrigami(product.id);
  });
}

function fetchVotesForOrigami(origamiId) {
  fetch(`/api/origamis/${origamiId}/votes`)
    .then((response) => response.json())
    .then((votes) => {
      let votesElem = document.querySelector(`#votes-${origamiId}`);
      votesElem.textContent = `Votes: ${votes}`;
    });
}

async function submitVote(productId) {
  if (!votingServiceAvailable) {
    alert('Voting service is currently unavailable. Please try again later.');
    return;
  }

  try {
    console.log(`Submitting vote for product ID: ${productId}`);

    // Use the correct voting service endpoint through frontend proxy
    const response = await fetch(`/api/origamis/${productId}/vote`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    console.log(`Vote response status: ${response.status}`);

    if (response.ok) {
      // Successfully submitted vote - reload products to show updated counts
      await loadProducts();
    } else {
      // Failed to submit vote - get detailed error message
      console.log('Vote submission failed');
      const errorText = await response.text();
      console.error('Error response:', errorText);

      let errorMessage = 'Vote did not get registered';
      if (errorText) {
        try {
          const errorObj = JSON.parse(errorText);
          errorMessage = errorObj.message || errorObj.error || errorText;
        } catch (e) {
          errorMessage = errorText;
        }
      }

      alert(`Error: ${errorMessage}`);
    }
  } catch (error) {
    console.error('Network or fetch error:', error);
    alert('Failed to submit vote. Please check your network connection and try again.');
  }
}

function shortenDescription(description, length = 100) {
  if (description.length > length) {
    return `${description.substring(0, length)}...`;
  } else {
    return description;
  }
}

function fetchServiceStatus() {
  fetch('/api/service-status')
    .then((response) => response.json())
    .then((data) => {
      renderServiceStatus(data);
    })
    .catch((error) => {
      console.error('Error fetching service status:', error);
    });
}

function renderServiceStatus(status) {
  const statusGrid = document.getElementById('status-grid');
  // statusGrid.innerHTML = ''; // clear the existing items

  Object.keys(status).forEach((service) => {
    const statusBox = document.createElement('div');
    statusBox.className = `status-box ${status[service]}`;
    statusBox.innerHTML = `
      <h4>${capitalizeFirstLetter(service)}</h4>
      <p>${capitalizeFirstLetter(status[service])}</p>
    `;
    statusGrid.appendChild(statusBox);
  });
}

function capitalizeFirstLetter(string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
}

function fetchDailyOrigami() {
  fetch('/daily-origami')
    .then((response) => {
      if (!response.ok) {
        throw new Error('Network response was not ok ' + response.statusText);
      }
      return response.json();
    })
    .then((data) => {
      renderDailyOrigami(data);
    })
    .catch((error) => {
      console.error('Error fetching the daily origami:', error);
      renderDailyOrigamiFallback();
    });
}

function renderDailyOrigami(data) {
  // Get the container where the origami should be displayed
  const origamiContainer = document.getElementById('daily-origami-container');

  // Clear any existing content
  origamiContainer.innerHTML = '';

  // Create and add a header
  const header = document.createElement('h2');
  header.innerText = 'Origami of the Day';
  origamiContainer.appendChild(header);

  // Create new HTML elements and set their properties
  const img = document.createElement('img');
  img.src = data.image_url;
  img.alt = 'Daily Origami';

  const description = document.createElement('p');
  description.innerText = data.description;

  const name = document.createElement('h2');
  name.innerText = data.name;

  // Append the new elements to the container
  origamiContainer.appendChild(img);
  origamiContainer.appendChild(name);
  origamiContainer.appendChild(description);
}

function renderDailyOrigamiFallback() {
  // Get the container where the origami should be displayed
  const origamiContainer = document.getElementById('daily-origami-container');

  // Clear any existing content
  origamiContainer.innerHTML = '';

  // Add a fallback message
  origamiContainer.innerHTML =
    '<p>Sorry, the recommendation engine is not available at the moment.</p>';
}

function checkRecommendationStatus() {
  fetch('/recommendation-status')
    .then((response) => response.json())
    .then((data) => {
      renderRecommendationStatus(data);
    })
    .catch((error) => {
      console.error('Error fetching recommendation service status:', error);
    });
}

function renderRecommendationStatus(status) {
  const statusGrid = document.getElementById('status-grid');

  const statusBox = document.createElement('div');
  statusBox.className = `status-box ${status.status}`;
  statusBox.innerHTML = `
    <h4>Recommendation</h4>
    <p>${capitalizeFirstLetter(status.status)}</p>
  `;
  statusGrid.appendChild(statusBox);
}

function checkVotingServiceStatus() {
  return fetch('/votingservice-status')
    .then((response) => {
      if (response.ok) {
        votingServiceAvailable = true;
        return response.json();
      } else {
        votingServiceAvailable = false;
        throw new Error('Service not available'); // Throwing an error to be caught in the catch block
      }
    })
    .then((data) => {
      renderVotingServiceStatus(data);
    })
    .catch((error) => {
      console.error('Error fetching voting service status:', error);
      votingServiceAvailable = false;
    });
}

function renderVotingServiceStatus(status) {
  const statusGrid = document.getElementById('status-grid');

  const statusBox = document.createElement('div');
  statusBox.className = `status-box ${status.status}`;
  statusBox.innerHTML = `
    <h4>Voting</h4>
    <p>${capitalizeFirstLetter(status.status)}</p>
  `;
  statusGrid.appendChild(statusBox);
}
