<template>
  <div class="slide-list">
    <h2>Uploaded Slides</h2>
    <div v-if="loading" class="loading">Loading slides...</div>
    <div v-else-if="slides.length === 0" class="no-slides">
      No slides uploaded yet.
    </div>
    <div v-else class="slides-grid">
      <div 
        v-for="slide in slides" 
        :key="slide.id" 
        class="slide-card"
        :class="{ 'selected': selectedSlideId === slide.id }"
        @click="selectSlide(slide.id)"
      >
        <div class="slide-header">
          <h3 class="slide-filename">{{ slide.filename }}</h3>
          <button @click.stop="deleteSlide(slide.id)" class="delete-btn" title="Delete slide">
            ✕
          </button>
        </div>
        <div class="slide-meta">
          <p><strong>ID:</strong> {{ slide.id.substring(0, 8) }}...</p>
          <p><strong>Size:</strong> {{ formatFileSize(slide.file_size) }}</p>
          <p><strong>Uploaded:</strong> {{ formatDate(slide.upload_date) }}</p>
        </div>
        <div class="slide-actions">
          <button @click.stop="viewSlide(slide.id)" class="action-btn view-btn">
            View
          </button>
          <button @click.stop="selectForInference(slide.id)" class="action-btn select-btn">
            Select for Inference
          </button>
        </div>
      </div>
    </div>
    <div v-if="error" class="error-message">{{ error }}</div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'SlideList',
  data() {
    return {
      slides: [],
      loading: false,
      error: '',
      selectedSlideId: null,
    };
  },
  mounted() {
    this.fetchSlides();
  },
  methods: {
    async fetchSlides() {
      this.loading = true;
      this.error = '';
      try {
        const response = await axios.get('http://localhost:8000/slides');
        this.slides = response.data;
      } catch (error) {
        this.handleApiError(error, 'Failed to fetch slides.');
      } finally {
        this.loading = false;
      }
    },
    async deleteSlide(slideId) {
      if (!confirm('Are you sure you want to delete this slide?')) {
        return;
      }
      
      try {
        await axios.delete(`http://localhost:8000/slides/${slideId}`);
        this.slides = this.slides.filter(slide => slide.id !== slideId);
        if (this.selectedSlideId === slideId) {
          this.selectedSlideId = null;
        }
      } catch (error) {
        this.handleApiError(error, 'Failed to delete slide.');
      }
    },
    selectSlide(slideId) {
      this.selectedSlideId = slideId;
      this.$emit('slide-selected', slideId);
    },
    viewSlide(slideId) {
      this.selectSlide(slideId);
    },
    selectForInference(slideId) {
      this.$emit('slide-selected-for-inference', slideId);
    },
    formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleDateString() + ' ' + 
             new Date(dateString).toLocaleTimeString();
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
  },
};
</script>

<style scoped>
.slide-list {
  margin: 20px;
  padding: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  background: #fafafa;
}

.loading {
  text-align: center;
  padding: 20px;
  color: #666;
}

.no-slides {
  text-align: center;
  padding: 40px;
  color: #999;
  font-style: italic;
}

.slides-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.slide-card {
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  background: white;
  cursor: pointer;
  transition: all 0.3s ease;
}

.slide-card:hover {
  border-color: #2196F3;
  box-shadow: 0 4px 12px rgba(33, 150, 243, 0.15);
  transform: translateY(-2px);
}

.slide-card.selected {
  border-color: #2196F3;
  background: #f3f9ff;
}

.slide-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.slide-filename {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  word-break: break-all;
  flex: 1;
  margin-right: 8px;
}

.delete-btn {
  background: #ff4444;
  color: white;
  border: none;
  border-radius: 4px;
  width: 24px;
  height: 24px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.delete-btn:hover {
  background: #cc0000;
}

.slide-meta {
  margin-bottom: 16px;
  font-size: 14px;
  color: #666;
}

.slide-meta p {
  margin: 4px 0;
}

.slide-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  flex: 1;
}

.view-btn {
  background: #2196F3;
  color: white;
}

.view-btn:hover {
  background: #1976D2;
}

.select-btn {
  background: #4CAF50;
  color: white;
}

.select-btn:hover {
  background: #45a049;
}

.error-message {
  color: #f44336;
  margin-top: 16px;
  padding: 12px;
  background: #ffebee;
  border-radius: 4px;
  border-left: 4px solid #f44336;
}
</style>
