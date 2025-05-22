<template>
  <div class="inference-panel">
    <h2>Run Inference</h2>
    <div class="form-group">
      <label for="slide-ids">Slide IDs (comma-separated):</label>
      <input type="text" id="slide-ids" v-model="slideIdsInput" placeholder="e.g., id1,id2,id3" />
    </div>
    <div class="form-group">
      <label for="model-select">Select Model:</label>
      <select id="model-select" v-model="selectedModel">
        <option disabled value="">Please select one</option>
        <option v-for="model in availableModels" :key="model.id" :value="model.id">
          {{ model.name }}
        </option>
      </select>
    </div>
    <button @click="runInference" :disabled="!canSubmitInference || submittingInference">
      {{ submittingInference ? 'Submitting...' : 'Run Inference' }}
    </button>
    <div v-if="inferenceJob" class="job-status">
      <h3>Inference Job Status</h3>
      <p>Job ID: {{ inferenceJob.job_id }}</p>
      <p>Status: {{ inferenceJob.status }}</p>
      <p>Model: {{ inferenceJob.model_name }}</p>
      <p>Slide IDs: {{ inferenceJob.slide_ids.join(', ') }}</p>
      <p v-if="inferenceJob.message">Message: {{ inferenceJob.message }}</p>
      <button @click="checkJobStatus(inferenceJob.job_id)" :disabled="checkingStatus">
        {{ checkingStatus ? 'Checking...' : 'Refresh Status' }}
      </button>
    </div>
    <p v-if="inferenceError" class="error-message">{{ inferenceError }}</p>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'InferencePanel',
  data() {
    return {
      slideIdsInput: '',
      selectedModel: '',
      availableModels: [ // Placeholder models
        { id: 'ctranspath', name: 'CtransPath V1' },
        { id: 'phikon', name: 'Phikon V1' },
        { id: 'uni', name: 'UNI V1 (Legacy)' },
      ],
      submittingInference: false,
      checkingStatus: false,
      inferenceJob: null,
      inferenceError: '',
    };
  },
  computed: {
    parsedSlideIds() {
      return this.slideIdsInput.split(',').map(id => id.trim()).filter(id => id);
    },
    canSubmitInference() {
      return this.parsedSlideIds.length > 0 && this.selectedModel;
    }
  },
  methods: {
    async runInference() {
      if (!this.canSubmitInference) {
        this.inferenceError = 'Please enter valid Slide IDs and select a model.';
        return;
      }
      this.submittingInference = true;
      this.inferenceError = '';
      this.inferenceJob = null;

      try {
        const response = await axios.post('http://localhost:8000/inference', {
          slide_ids: this.parsedSlideIds,
          model_name: this.selectedModel,
        });
        this.inferenceJob = response.data;
      } catch (error) {
        this.handleApiError(error, 'Failed to start inference job.');
      } finally {
        this.submittingInference = false;
      }
    },
    async checkJobStatus(jobId) {
      if (!jobId) return;
      this.checkingStatus = true;
      this.inferenceError = ''; // Clear previous errors specific to job status check

      try {
        const response = await axios.get(`http://localhost:8000/inference/${jobId}`);
        this.inferenceJob = response.data; // Update the job details
      } catch (error) {
         if (error.response && error.response.status === 404) {
            this.inferenceError = `Job ID ${jobId} not found. It might still be processing or there was an issue.`;
            // Optionally clear inferenceJob or handle as per application logic
            // this.inferenceJob = null; 
        } else {
            this.handleApiError(error, `Failed to check status for job ${jobId}.`);
        }
      } finally {
        this.checkingStatus = false;
      }
    },
    handleApiError(error, defaultMessage) {
      if (error.response) {
        this.inferenceError = `Error: ${error.response.data.detail || defaultMessage}`;
      } else if (error.request) {
        this.inferenceError = 'Error: No response from server. Is the backend running?';
      } else {
        this.inferenceError = `Error: ${error.message}`;
      }
    }
  },
};
</script>

<style scoped>
.inference-panel {
  margin: 20px;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
}
.form-group {
  margin-bottom: 15px;
}
.form-group label {
  display: block;
  margin-bottom: 5px;
}
.form-group input[type="text"],
.form-group select {
  width: 100%;
  padding: 8px;
  box-sizing: border-box;
}
.job-status {
  margin-top: 20px;
  padding: 15px;
  border: 1px solid #eee;
  background-color: #f9f9f9;
}
.error-message {
  color: red;
  margin-top: 10px;
}
</style>
