<template>
  <div class="results-display">
    <h2>Inference Results</h2>
    
    <div v-if="!currentJobId" class="no-results">
      No results to display. Run an inference job first.
    </div>
    
    <div v-else-if="loading" class="loading">
      Loading results...
    </div>
    
    <div v-else-if="error" class="error-message">
      {{ error }}
    </div>
    
    <div v-else-if="results" class="results-container">
      <div class="results-header">
        <h3>Job ID: {{ currentJobId }}</h3>
        <p>Status: <span class="status-completed">{{ results.status }}</span></p>
        <p>Total Slides: {{ results.results.length }}</p>
      </div>
      
      <div class="slides-results">
        <div 
          v-for="(slideResult, index) in results.results" 
          :key="slideResult.slide_id"
          class="slide-result-card"
        >
          <div class="slide-result-header">
            <h4>{{ getSlideFilename(slideResult.slide_id) }}</h4>
            <span class="slide-id">ID: {{ slideResult.slide_id.substring(0, 8) }}...</span>
          </div>
          
          <div v-if="slideResult.error" class="slide-error">
            <p><strong>Error:</strong> {{ slideResult.error }}</p>
          </div>
          
          <div v-else class="slide-predictions">
            <h5>Class Predictions:</h5>
            <div class="predictions-list">
              <div 
                v-for="prediction in slideResult.predictions" 
                :key="prediction.class_name"
                class="prediction-item"
              >
                <div class="prediction-header">
                  <span class="class-name">{{ prediction.class_name }}</span>
                  <span class="probability">{{ (prediction.probability * 100).toFixed(2) }}%</span>
                </div>
                <div class="probability-bar">
                  <div 
                    class="probability-fill" 
                    :style="{ width: (prediction.probability * 100) + '%' }"
                  ></div>
                </div>
              </div>
            </div>
            
            <div v-if="slideResult.attention" class="attention-info">
              <h5>Attention Information:</h5>
              <p>Attention weights available ({{ slideResult.attention.length }} patches)</p>
              <button @click="showAttentionDetails(slideResult)" class="view-attention-btn">
                View Attention Map
              </button>
            </div>
            
            <div v-if="slideResult.patch_coordinates" class="patch-info">
              <h5>Patch Information:</h5>
              <p>Total patches analyzed: {{ slideResult.patch_coordinates.length }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Attention Map Modal -->
    <div v-if="showAttentionModal" class="modal-overlay" @click="closeAttentionModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Attention Map - {{ selectedSlideForAttention?.slide_id }}</h3>
          <button @click="closeAttentionModal" class="close-btn">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="selectedSlideForAttention" class="attention-visualization">
            <p>Attention weights for {{ selectedSlideForAttention.attention.length }} patches</p>
            <div class="attention-stats">
              <p><strong>Min attention:</strong> {{ getAttentionStats(selectedSlideForAttention.attention).min.toFixed(4) }}</p>
              <p><strong>Max attention:</strong> {{ getAttentionStats(selectedSlideForAttention.attention).max.toFixed(4) }}</p>
              <p><strong>Mean attention:</strong> {{ getAttentionStats(selectedSlideForAttention.attention).mean.toFixed(4) }}</p>
            </div>
            <!-- Here you could add a more sophisticated visualization -->
            <div class="attention-heatmap-placeholder">
              <p>Attention heatmap visualization would go here</p>
              <p>(Requires additional visualization library like D3.js or Chart.js)</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'ResultsDisplay',
  props: {
    jobId: {
      type: String,
      default: null
    },
    slides: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      currentJobId: null,
      results: null,
      loading: false,
      error: '',
      showAttentionModal: false,
      selectedSlideForAttention: null
    };
  },
  watch: {
    jobId(newJobId) {
      if (newJobId) {
        this.loadResults(newJobId);
      }
    }
  },
  methods: {
    async loadResults(jobId) {
      this.currentJobId = jobId;
      this.loading = true;
      this.error = '';
      this.results = null;
      
      try {
        const response = await axios.get(`http://localhost:8000/inference/results/${jobId}`);
        this.results = response.data;
      } catch (error) {
        if (error.response && error.response.status === 202) {
          this.error = 'Results are not ready yet. Please wait for the inference to complete.';
        } else {
          this.handleApiError(error, 'Failed to load results.');
        }
      } finally {
        this.loading = false;
      }
    },
    getSlideFilename(slideId) {
      const slide = this.slides.find(s => s.id === slideId);
      return slide ? slide.filename : `Unknown Slide (${slideId.substring(0, 8)}...)`;
    },
    showAttentionDetails(slideResult) {
      this.selectedSlideForAttention = slideResult;
      this.showAttentionModal = true;
    },
    closeAttentionModal() {
      this.showAttentionModal = false;
      this.selectedSlideForAttention = null;
    },
    getAttentionStats(attention) {
      const flatAttention = attention.flat();
      return {
        min: Math.min(...flatAttention),
        max: Math.max(...flatAttention),
        mean: flatAttention.reduce((a, b) => a + b, 0) / flatAttention.length
      };
    },
    handleApiError(error, defaultMessage) {
      if (error.response) {
        this.error = `Error: ${error.response.data.detail || defaultMessage}`;
      } else if (error.request) {
        this.error = 'Error: No response from server. Is the backend running?';
      } else {
        this.error = `Error: ${error.message}`;
      }
    }
  }
};
</script>

<style scoped>
.results-display {
  margin: 20px;
  padding: 24px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  background: #fafafa;
}

.no-results {
  text-align: center;
  padding: 40px;
  color: #999;
  font-style: italic;
}

.loading {
  text-align: center;
  padding: 20px;
  color: #666;
}

.results-header {
  margin-bottom: 24px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.results-header h3 {
  margin: 0 0 8px 0;
  color: #333;
}

.results-header p {
  margin: 4px 0;
  color: #666;
}

.status-completed {
  color: #4CAF50;
  font-weight: 600;
}

.slides-results {
  display: grid;
  gap: 20px;
}

.slide-result-card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
}

.slide-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.slide-result-header h4 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.slide-id {
  color: #666;
  font-size: 14px;
}

.slide-error {
  padding: 12px;
  background: #ffebee;
  border-radius: 6px;
  border-left: 4px solid #f44336;
}

.slide-error p {
  margin: 0;
  color: #d32f2f;
}

.slide-predictions h5 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 16px;
}

.predictions-list {
  margin-bottom: 20px;
}

.prediction-item {
  margin-bottom: 12px;
}

.prediction-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.class-name {
  font-weight: 600;
  color: #333;
}

.probability {
  font-weight: 600;
  color: #2196F3;
}

.probability-bar {
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.probability-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #2196F3);
  transition: width 0.3s ease;
}

.attention-info, .patch-info {
  margin-top: 20px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 6px;
}

.attention-info h5, .patch-info h5 {
  margin: 0 0 8px 0;
  color: #333;
}

.attention-info p, .patch-info p {
  margin: 4px 0;
  color: #666;
}

.view-attention-btn {
  margin-top: 8px;
  padding: 8px 16px;
  background: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.view-attention-btn:hover {
  background: #1976D2;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 800px;
  max-height: 80vh;
  overflow-y: auto;
  margin: 20px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.close-btn {
  background: #f44336;
  color: white;
  border: none;
  border-radius: 4px;
  width: 32px;
  height: 32px;
  cursor: pointer;
  font-size: 16px;
}

.modal-body {
  padding: 20px;
}

.attention-stats {
  margin: 16px 0;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
}

.attention-stats p {
  margin: 4px 0;
  color: #666;
}

.attention-heatmap-placeholder {
  margin-top: 20px;
  padding: 40px;
  background: #f0f0f0;
  border-radius: 6px;
  text-align: center;
  color: #666;
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
