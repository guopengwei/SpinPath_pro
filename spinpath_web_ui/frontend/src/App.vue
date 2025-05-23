<template>
  <div id="app">
    <header class="app-header">
      <div class="header-content">
        <img alt="SpinPath logo" src="./assets/logo.png" class="logo">
        <h1>SpinPath Web UI</h1>
        <p class="subtitle">Whole Slide Image Analysis with Deep Learning</p>
      </div>
    </header>

    <main class="app-main">
      <div class="main-grid">
        <!-- Left Column: Upload and Slides -->
        <div class="left-column">
          <SlideUpload @upload-success="refreshSlideList" />
          <SlideList 
            ref="slideListComponent" 
            @slide-selected="viewSlide" 
            @slide-selected-for-inference="addSlideForInference"
          />
        </div>

        <!-- Right Column: Inference and Results -->
        <div class="right-column">
          <InferencePanel 
            ref="inferencePanel"
            :slides="slides"
            @view-results="viewResults"
          />
          <ResultsDisplay 
            :job-id="currentResultsJobId"
            :slides="slides"
          />
        </div>
      </div>

      <!-- Image Viewer Modal -->
      <div v-if="currentSlideIdForViewer" class="modal-overlay" @click="closeImageViewer">
        <div class="modal-content image-viewer-modal" @click.stop>
          <div class="modal-header">
            <h3>Slide Viewer - {{ getCurrentSlideFilename() }}</h3>
            <button @click="closeImageViewer" class="close-btn">✕</button>
          </div>
          <div class="modal-body">
            <ImageViewer :slide-id="currentSlideIdForViewer" />
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import SlideUpload from './components/SlideUpload.vue';
import SlideList from './components/SlideList.vue';
import ImageViewer from './components/ImageViewer.vue';
import InferencePanel from './components/InferencePanel.vue';
import ResultsDisplay from './components/ResultsDisplay.vue';

export default {
  name: 'App',
  components: {
    SlideUpload,
    SlideList,
    ImageViewer,
    InferencePanel,
    ResultsDisplay,
  },
  data() {
    return {
      currentSlideIdForViewer: null,
      currentResultsJobId: null,
      slides: []
    };
  },
  methods: {
    refreshSlideList() {
      this.$refs.slideListComponent.fetchSlides();
    },
    viewSlide(slideId) {
      this.currentSlideIdForViewer = slideId;
    },
    closeImageViewer() {
      this.currentSlideIdForViewer = null;
    },
    addSlideForInference(slideId) {
      if (this.$refs.inferencePanel) {
        this.$refs.inferencePanel.addSlideForInference(slideId);
      }
    },
    viewResults(jobId) {
      this.currentResultsJobId = jobId;
    },
    getCurrentSlideFilename() {
      if (!this.currentSlideIdForViewer) return '';
      const slide = this.slides.find(s => s.id === this.currentSlideIdForViewer);
      return slide ? slide.filename : 'Unknown Slide';
    }
  },
  watch: {
    // Watch for changes in slide list from SlideList component
    '$refs.slideListComponent.slides': {
      handler(newSlides) {
        if (newSlides) {
          this.slides = newSlides;
        }
      },
      deep: true
    }
  },
  mounted() {
    // Get initial slides data
    this.$nextTick(() => {
      if (this.$refs.slideListComponent) {
        this.slides = this.$refs.slideListComponent.slides;
      }
    });
  }
};
</script>

<style>
* {
  box-sizing: border-box;
}

#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.app-header {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding: 20px 0;
  text-align: center;
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.1);
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.logo {
  height: 60px;
  margin-bottom: 10px;
}

.app-header h1 {
  margin: 10px 0 5px 0;
  font-size: 2.5rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  margin: 0;
  color: #666;
  font-size: 1.1rem;
  font-weight: 300;
}

.app-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30px;
  align-items: start;
}

.left-column, .right-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(5px);
}

.modal-content {
  background: white;
  border-radius: 12px;
  max-width: 90vw;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.image-viewer-modal {
  max-width: 95vw;
  max-height: 95vh;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.modal-header h3 {
  margin: 0;
  color: #333;
  font-size: 1.25rem;
}

.close-btn {
  background: #f44336;
  color: white;
  border: none;
  border-radius: 6px;
  width: 36px;
  height: 36px;
  cursor: pointer;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.close-btn:hover {
  background: #d32f2f;
}

.modal-body {
  padding: 0;
  overflow: auto;
  max-height: calc(90vh - 80px);
}

/* Responsive Design */
@media (max-width: 1200px) {
  .main-grid {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  
  .app-header h1 {
    font-size: 2rem;
  }
}

@media (max-width: 768px) {
  .app-main {
    padding: 10px;
  }
  
  .header-content {
    padding: 0 10px;
  }
  
  .app-header h1 {
    font-size: 1.75rem;
  }
  
  .subtitle {
    font-size: 1rem;
  }
  
  .modal-content {
    margin: 10px;
    max-width: calc(100vw - 20px);
    max-height: calc(100vh - 20px);
  }
}

/* Component overrides for better integration */
.slide-list, .inference-panel, .results-display {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.slide-upload {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  margin: 0;
  border-radius: 12px;
  padding: 24px;
}
</style>
