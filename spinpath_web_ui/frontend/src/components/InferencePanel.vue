<template>
  <div class="inference-panel">
    <h2>Run Inference</h2>
    
    <div class="model-selection">
      <label for="model-select">Select Model:</label>
      <select id="model-select" v-model="selectedModel" :disabled="loadingModels">
        <option disabled value="">{{ loadingModels ? 'Loading models...' : 'Please select a model' }}</option>
        <option v-for="model in availableModels" :key="model.id" :value="model.id">
          {{ model.name }}
        </option>
      </select>
      <p v-if="selectedModelDetails" class="model-description">
        {{ selectedModelDetails.description }}
      </p>
    </div>

    <div class="slide-selection">
      <label>Selected Slides for Inference:</label>
      <div v-if="selectedSlideIds.length === 0" class="no-selection">
        No slides selected. Click "Select for Inference" on slides in the slide list.
      </div>
      <div v-else class="selected-slides">
        <div v-for="slideId in selectedSlideIds" :key="slideId" class="selected-slide">
          <span>{{ getSlideFilename(slideId) }}</span>
          <button @click="removeSlide(slideId)" class="remove-btn">✕</button>
        </div>
      </div>
    </div>

    <div class="inference-settings">
      <div class="setting-group">
        <label for="patch-size">Patch Size (μm):</label>
        <input 
          type="number" 
          id="patch-size" 
          v-model.number="patchSizeUm" 
          min="64" 
          max="1024" 
          step="32"
        />
      </div>
      <div class="setting-group">
        <label for="num-workers">Number of Workers:</label>
        <input 
          type="number" 
          id="num-workers" 
          v-model.number="numWorkers" 
          min="1" 
          max="16" 
          step="1"
        />
      </div>
    </div>

    <button 
      @click="runInference" 
      :disabled="!canSubmitInference || submittingInference"
      class="run-inference-btn"
    >
      {{ submittingInference ? 'Starting Inference...' : 'Run Inference' }}
    </button>

    <div v-if="inferenceJob" class="job-status">
      <h3>Inference Job Status</h3>
      <div class="job-info">
        <p><strong>Job ID:</strong> {{ inferenceJob.job_id }}</p>
        <p><strong>Status:</strong> 
          <span :class="getStatusClass(inferenceJob.status)">
            {{ inferenceJob.status }}
          </span>
        </p>
        <p><strong>Model:</strong> {{ getModelName(inferenceJob.model_id) }}</p>
        <p><strong>Slides:</strong> {{ inferenceJob.slide_ids.length }} slides</p>
        <p v-if="inferenceJob.progress !== null"><strong>Progress:</strong> {{ Math.round(inferenceJob.progress * 100) }}%</p>
        <p v-if="inferenceJob.message"><strong>Message:</strong> {{ inferenceJob.message }}</p>
      </div>
      
      <div v-if="inferenceJob.progress !== null && inferenceJob.status === 'RUNNING'" class="progress-bar">
        <div class="progress-fill" :style="{ width: (inferenceJob.progress * 100) + '%' }"></div>
      </div>

      <div class="job-actions">
        <button @click="checkJobStatus(inferenceJob.job_id)" :disabled="checkingStatus" class="refresh-btn">
          {{ checkingStatus ? 'Checking...' : 'Refresh Status' }}
        </button>
        <button 
          v-if="inferenceJob.status === 'COMPLETED'" 
          @click="viewResults(inferenceJob.job_id)"
          class="view-results-btn"
        >
          View Results
        </button>
      </div>
    </div>

    <div v-if="inferenceError" class="error-message">{{ inferenceError }}</div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'InferencePanel',
  props: {
    slides: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      selectedSlideIds: [],
      selectedModel: '',
      availableModels: [],
      loadingModels: false,
      patchSizeUm: 256,
      numWorkers: 4,
      submittingInference: false,
      checkingStatus: false,
      inferenceJob: null,
      inferenceError: '',
    };
  },
  computed: {
    selectedModelDetails() {
      return this.availableModels.find(model => model.id === this.selectedModel);
    },
    canSubmitInference() {
      return this.selectedSlideIds.length > 0 && this.selectedModel && !this.loadingModels;
    }
  },
  mounted() {
    this.fetchAvailableModels();
  },
  methods: {
    async fetchAvailableModels() {
      this.loadingModels = true;
      try {
        const response = await axios.get('http://localhost:8000/models');
        this.availableModels = response.data;
      } catch (error) {
        this.handleApiError(error, 'Failed to fetch available models.');
      } finally {
        this.loadingModels = false;
      }
    },
    addSlideForInference(slideId) {
      if (!this.selectedSlideIds.includes(slideId)) {
        this.selectedSlideIds.push(slideId);
      }
    },
    removeSlide(slideId) {
      const index = this.selectedSlideIds.indexOf(slideId);
      if (index > -1) {
        this.selectedSlideIds.splice(index, 1);
      }
    },
    getSlideFilename(slideId) {
      const slide = this.slides.find(s => s.id === slideId);
      return slide ? slide.filename : `Unknown (${slideId.substring(0, 8)}...)`;
    },
    getModelName(modelId) {
      const model = this.availableModels.find(m => m.id === modelId);
      return model ? model.name : modelId;
    },
    getStatusClass(status) {
      return {
        'status-pending': status === 'PENDING',
        'status-running': status === 'RUNNING', 
        'status-completed': status === 'COMPLETED',
        'status-failed': status === 'FAILED'
      };
    },
    async runInference() {
      if (!this.canSubmitInference) {
        this.inferenceError = 'Please select slides and a model.';
        return;
      }
      
      this.submittingInference = true;
      this.inferenceError = '';
      this.inferenceJob = null;

      try {
        const response = await axios.post('http://localhost:8000/inference', {
          slide_ids: this.selectedSlideIds,
          model_id: this.selectedModel,
          patch_size_um: this.patchSizeUm,
          num_workers: this.numWorkers
        });
        this.inferenceJob = response.data;
        
        // Start polling for status updates
        this.startStatusPolling();
      } catch (error) {
        this.handleApiError(error, 'Failed to start inference job.');
      } finally {
        this.submittingInference = false;
      }
    },
    async checkJobStatus(jobId) {
      if (!jobId) return;
      this.checkingStatus = true;
      
      try {
        const response = await axios.get(`http://localhost:8000/inference/${jobId}`);
        this.inferenceJob = response.data;
      } catch (error) {
        if (error.response && error.response.status === 404) {
          this.inferenceError = `Job ID ${jobId} not found.`;
        } else {
          this.handleApiError(error, `Failed to check status for job ${jobId}.`);
        }
      } finally {
        this.checkingStatus = false;
      }
    },
    startStatusPolling() {
      const poll = () => {
        if (this.inferenceJob && 
            (this.inferenceJob.status === 'PENDING' || this.inferenceJob.status === 'RUNNING')) {
          this.checkJobStatus(this.inferenceJob.job_id);
          setTimeout(poll, 2000); // Poll every 2 seconds
        }
      };
      setTimeout(poll, 2000);
    },
    viewResults(jobId) {
      this.$emit('view-results', jobId);
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
  padding: 24px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  background: #fafafa;
}

.model-selection {
  margin-bottom: 24px;
}

.model-selection label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #333;
}

.model-selection select {
  width: 100%;
  padding: 12px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 16px;
  background: white;
}

.model-description {
  margin-top: 8px;
  font-size: 14px;
  color: #666;
  font-style: italic;
}

.slide-selection {
  margin-bottom: 24px;
}

.slide-selection label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #333;
}

.no-selection {
  padding: 16px;
  background: #f5f5f5;
  border-radius: 6px;
  color: #666;
  text-align: center;
  font-style: italic;
}

.selected-slides {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.selected-slide {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #e3f2fd;
  border: 1px solid #2196F3;
  border-radius: 20px;
  font-size: 14px;
}

.remove-btn {
  background: #f44336;
  color: white;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.inference-settings {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.setting-group label {
  display: block;
  margin-bottom: 4px;
  font-weight: 600;
  color: #333;
}

.setting-group input {
  width: 100%;
  padding: 8px 12px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
}

.run-inference-btn {
  width: 100%;
  padding: 16px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.3s;
}

.run-inference-btn:hover:not(:disabled) {
  background: #45a049;
}

.run-inference-btn:disabled {
  background: #cccccc;
  cursor: not-allowed;
}

.job-status {
  margin-top: 24px;
  padding: 20px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  background: white;
}

.job-info p {
  margin: 8px 0;
}

.status-pending { color: #ff9800; }
.status-running { color: #2196F3; }
.status-completed { color: #4CAF50; }
.status-failed { color: #f44336; }

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  margin: 16px 0;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #2196F3;
  transition: width 0.3s ease;
}

.job-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.refresh-btn {
  padding: 8px 16px;
  background: #2196F3;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.view-results-btn {
  padding: 8px 16px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.error-message {
  color: #f44336;
  margin-top: 16px;
  padding: 12px;
  background: #ffebee;
  border-radius: 6px;
  border-left: 4px solid #f44336;
}
</style>
