const express = require('express');
const axios = require('axios');
const os = require('os');
const fs = require('fs');
const config = require('./config.json'); // Import configuration
const app = express();
const productsApiBaseUri = config.productsApiBaseUri;
const recommendationBaseUri = config.recommendationBaseUri;
const votingBaseUri = config.votingBaseUri;
const origamisRouter = require('./routes/origamis');

app.set('view engine', 'ejs');
app.use(express.static('public'));
app.use('/api/origamis', origamisRouter);

// Static Middleware
app.use('/static', express.static('public'));

// Endpoint to serve product data to client
app.get('/api/products', async (req, res) => {
  try {
    const response = await axios.get(`${productsApiBaseUri}/api/products`);
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching products:', error);
    res.status(500).send('Error fetching products');
  }
});

app.get('/', (req, res) => {
  // Gather system info
  const systemInfo = {
    hostname: os.hostname(),
    ipAddress: getIPAddress(),
    isContainer: isContainer(),
    isKubernetes: fs.existsSync('/var/run/secrets/kubernetes.io'),
  };

  res.render('index', {
    systemInfo,
    app_version: config.version, // provide version to the view
  });
});

function getIPAddress() {
  // Logic to fetch IP Address
  const networkInterfaces = os.networkInterfaces();
  return (networkInterfaces['eth0'] && networkInterfaces['eth0'][0].address) || 'IP not found';
}

function isContainer() {
  // Logic to check if running in a container
  try {
    fs.readFileSync('/proc/1/cgroup');
    return true;
  } catch {
    return false;
  }
}

app.get('/api/service-status', async (req, res) => {
  try {
    // Example of checking the status of the products service
    await axios.get(`${productsApiBaseUri}/api/products`);

    // If code execution reaches here, the service(s) are up
    res.json({ Catalogue: 'up' });
  } catch (error) {
    console.error('Error:', error);
    res.json({ Catalogue: 'down' });
  }
});

app.get('/recommendation-status', async (req, res) => {
  try {
    await axios.get(`${recommendationBaseUri}/api/recommendation-status`);
    res.json({ status: 'up', message: 'Recommendation Service is Online' });
  } catch {
    res.json({ status: 'down', message: 'Recommendation Service is Offline' });
  }
});

app.get('/votingservice-status', async (req, res) => {
  try {
    await axios.get(`${votingBaseUri}/api/origamis`);
    res.json({ status: 'up', message: 'Voting Service is Online' });
  } catch {
    res.json({ status: 'down', message: 'Voting Service is Offline' });
  }
});

app.get('/daily-origami', (req, res) => {
  axios
    .get(`${recommendationBaseUri}/api/origami-of-the-day`)
    .then((response) => {
      res.json(response.data);
    })
    .catch(() => {
      res.status(500).send('Error while fetching daily origami');
    });
});

// Handle 404
app.use((req, res) => {
  res.status(404).send('ERROR 404 - Not Found on This Server');
});

const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server is running on port ${PORT}`);
});

module.exports = server; // Note that we're exporting the server, not app.




