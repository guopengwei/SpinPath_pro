<template>
  <div class="results-display">
    <h2>View Inference Results</h2>
    <div class="form-group">
      <label for="job-id-input">Enter Job ID:</label>
      <input type="text" id="job-id-input" v-model="jobId" placeholder="Enter Job ID from Inference Panel" />
      <button @click="fetchResults" :disabled="!jobId || loadingResults">
        {{ loadingResults ? 'Loading...' : 'Get Results' }}
      </button>
    </div>
    <div v-if="results" class="results-content">
      <h3>Results for Job ID: {{ results.job_id }}</h3>
      <pre>{{ JSON.stringify(results.results, null, 2) }}</pre>
    </div>
    <p v-if="resultsError" class="error-message">{{ resultsError }}</p>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'ResultsDisplay',
  data() {
    return {
      jobId: '',
      results: null,
      loadingResults: false,
      resultsError: '',
    };
  },
  methods: {
    async fetchResults() {
      if (!this.jobId) {
        this.resultsError = 'Please enter a Job ID.';
        return;
      }
      this.loadingResults = true;
      this.resultsError = '';
      this.results = null;

      try {
        const response = await axios.get(`http://localhost:8000/inference/results/${this.jobId}`);
        if (response.data && response.data.job_id) {
            // Check if results are ready or just a status message
            if (response.data.results) {
                this.results = response.data;
            } else {
                // Backend might return a message if results are not ready, e.g. under a 'message' field
                this.resultsError = response.data.message || `Results for job ${this.jobId} are not ready or not available.`;
            }
        } else {
            // Handle cases where response might not be what's expected, though backend should give structured error
            this.resultsError = `Unexpected response format for job ${this.jobId}.`;
        }
      } catch (error) {
        if (error.response) {
          this.resultsError = `Error: ${error.response.data.detail || 'Failed to fetch results.'}`;
          if (error.response.status === 404) {
              this.resultsError = `Job ID ${this.jobId} not found, or results are not available.`;
          }
        } else if (error.request) {
          this.resultsError = 'Error: No response from server. Is the backend running?';
        } else {
          this.resultsError = `Error: ${error.message}`;
        }
      } finally {
        this.loadingResults = false;
      }
    },
  },
};
</script>

<style scoped>
.results-display {
  margin: 20px;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
}
.form-group {
  margin-bottom: 15px;
  display: flex;
  align-items: center;
}
.form-group label {
  margin-right: 10px;
}
.form-group input[type="text"] {
  flex-grow: 1;
  padding: 8px;
  margin-right: 10px;
}
.results-content {
  margin-top: 20px;
  padding: 15px;
  border: 1px solid #eee;
  background-color: #f9f9f9;
}
.results-content pre {
  white-space: pre-wrap; /* Allow text to wrap */
  word-wrap: break-word; /* Break long words */
  background-color: #fff;
  padding: 10px;
  border: 1px solid #ddd;
}
.error-message {
  color: red;
  margin-top: 10px;
}
</style>
