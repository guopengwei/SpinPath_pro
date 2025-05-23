<template>
  <div class="image-viewer-container">
    <!-- Viewer Controls -->
    <div class="viewer-controls" v-if="slideInfo">
      <div class="control-group">
        <button @click="zoomIn" class="control-btn" title="Zoom In">
          <i class="icon-zoom-in">🔍+</i>
        </button>
        <button @click="zoomOut" class="control-btn" title="Zoom Out">
          <i class="icon-zoom-out">🔍-</i>
        </button>
        <button @click="goHome" class="control-btn" title="Home">
          <i class="icon-home">🏠</i>
        </button>
        <button @click="fullScreen" class="control-btn" title="Full Screen">
          <i class="icon-fullscreen">⛶</i>
        </button>
      </div>
      
      <div class="control-group">
        <label for="level-select">Level:</label>
        <select id="level-select" v-model="selectedLevel" @change="changeLevel" class="level-select">
          <option v-for="(level, index) in slideInfo.level_count" :key="index" :value="index">
            Level {{ index }} ({{ slideInfo.level_dimensions[index][0] }}×{{ slideInfo.level_dimensions[index][1] }})
          </option>
        </select>
      </div>
      
      <div class="control-group info-display">
        <span class="info-item">{{ slideInfo.dimensions[0] }}×{{ slideInfo.dimensions[1] }}px</span>
        <span class="info-item" v-if="slideInfo.mpp_x">{{ slideInfo.mpp_x.toFixed(3) }} μm/px</span>
        <span class="info-item" v-if="slideInfo.objective_power">{{ slideInfo.objective_power }}×</span>
        <span class="info-item zoom-info">Zoom: {{ currentZoom }}%</span>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>Loading slide...</p>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="error-display">
      <h3>Error Loading Slide</h3>
      <p>{{ error }}</p>
      <button @click="retryLoad" class="retry-btn">Retry</button>
    </div>

    <!-- OpenSeadragon Viewer Container -->
    <div 
      ref="viewerContainer" 
      id="openseadragon-viewer" 
      class="viewer-container"
      :class="{ 'fullscreen': isFullscreen }"
    ></div>

    <!-- Slide Information Panel -->
    <div v-if="slideInfo && showInfo" class="info-panel">
      <h3>Slide Information</h3>
      <div class="info-grid">
        <div class="info-row">
          <span class="label">Format:</span>
          <span class="value">{{ slideInfo.slide_format }}</span>
        </div>
        <div class="info-row">
          <span class="label">Dimensions:</span>
          <span class="value">{{ slideInfo.dimensions[0] }} × {{ slideInfo.dimensions[1] }} pixels</span>
        </div>
        <div class="info-row">
          <span class="label">Levels:</span>
          <span class="value">{{ slideInfo.level_count }}</span>
        </div>
        <div class="info-row" v-if="slideInfo.mpp_x">
          <span class="label">Resolution:</span>
          <span class="value">{{ slideInfo.mpp_x.toFixed(3) }} × {{ slideInfo.mpp_y.toFixed(3) }} μm/pixel</span>
        </div>
        <div class="info-row" v-if="slideInfo.objective_power">
          <span class="label">Objective:</span>
          <span class="value">{{ slideInfo.objective_power }}×</span>
        </div>
        <div class="info-row">
          <span class="label">File Size:</span>
          <span class="value">{{ formatFileSize(slideInfo.file_size) }}</span>
        </div>
      </div>
      <button @click="showInfo = false" class="close-info-btn">Close</button>
    </div>

    <!-- Navigation Minimap -->
    <div v-if="viewer && showMinimap" class="minimap-container" ref="minimapContainer"></div>

    <!-- Annotation Overlay (for future implementation) -->
    <div v-if="viewer && annotations.length > 0" class="annotation-overlay">
      <!-- Annotations will be rendered here -->
    </div>
  </div>
</template>

<script>
// Import OpenSeadragon
import OpenSeadragon from 'openseadragon'

export default {
  name: 'ImageViewer',
  props: {
    slideId: {
      type: String,
      required: true
    },
    annotations: {
      type: Array,
      default: () => []
    },
    showControls: {
      type: Boolean,
      default: true
    },
    enableAnnotations: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      viewer: null,
      slideInfo: null,
      loading: false,
      error: null,
      selectedLevel: 0,
      currentZoom: 100,
      isFullscreen: false,
      showInfo: false,
      showMinimap: true,
      tileSourceConfig: null,
      viewerReady: false
    }
  },
  async mounted() {
    await this.initViewer()
  },
  beforeUnmount() {
    this.cleanup()
  },
  watch: {
    slideId: {
      handler: 'loadSlide',
      immediate: false
    }
  },
  methods: {
    async initViewer() {
      this.loading = true
      this.error = null

      try {
        // Load slide information
        await this.loadSlideInfo()
        
        // Initialize OpenSeadragon viewer
        this.setupOpenSeadragon()
        
        // Load the slide
        await this.loadSlide()
        
      } catch (error) {
        console.error('Error initializing viewer:', error)
        this.error = error.message || 'Failed to initialize viewer'
      } finally {
        this.loading = false
      }
    },

    async loadSlideInfo() {
      try {
        const response = await fetch(`/api/slides/${this.slideId}/info`)
        if (!response.ok) {
          throw new Error(`Failed to load slide info: ${response.statusText}`)
        }
        this.slideInfo = await response.json()
      } catch (error) {
        throw new Error(`Failed to load slide information: ${error.message}`)
      }
    },

    setupOpenSeadragon() {
      // OpenSeadragon configuration
      const config = {
        id: 'openseadragon-viewer',
        prefixUrl: 'https://cdn.jsdelivr.net/npm/openseadragon@3.1.0/build/openseadragon/images/',
        
        // Navigation and UI
        showNavigationControl: this.showControls,
        showZoomControl: true,
        showHomeControl: true,
        showFullPageControl: true,
        showRotationControl: false,
        showSequenceControl: false,
        navigationControlAnchor: OpenSeadragon.ControlAnchor.TOP_LEFT,
        
        // Zooming
        zoomInButton: 'zoom-in-btn',
        zoomOutButton: 'zoom-out-btn',
        homeButton: 'home-btn',
        fullPageButton: 'fullscreen-btn',
        minZoomLevel: 0.1,
        maxZoomLevel: 10,
        zoomPerClick: 2,
        zoomPerScroll: 1.2,
        
        // Performance
        immediateRender: false,
        blendTime: 0.1,
        alwaysBlend: false,
        showNavigator: this.showMinimap,
        navigatorPosition: 'BOTTOM_RIGHT',
        navigatorSizeRatio: 0.15,
        
        // Tiles
        preserveImageSizeOnResize: true,
        useCanvas: true,
        smoothTileEdgesMinZoom: 1.1,
        iOSDevice: /iPad|iPhone|iPod/.test(navigator.userAgent),
        
        // Custom tile source (will be set in loadSlide)
        tileSources: null
      }

      this.viewer = OpenSeadragon(config)
      
      // Set up event listeners
      this.setupEventListeners()
    },

    setupEventListeners() {
      if (!this.viewer) return

      // Zoom change handler
      this.viewer.addHandler('zoom', (event) => {
        this.currentZoom = Math.round(event.zoom * 100)
      })

      // Open handler
      this.viewer.addHandler('open', () => {
        this.viewerReady = true
        this.$emit('viewer-ready', this.viewer)
      })

      // Tile load handlers for performance monitoring
      let tilesLoading = 0
      let tilesLoaded = 0

      this.viewer.addHandler('tile-load-failed', (event) => {
        console.warn('Tile load failed:', event)
      })

      this.viewer.addHandler('tile-loading', () => {
        tilesLoading++
      })

      this.viewer.addHandler('tile-loaded', () => {
        tilesLoaded++
        if (tilesLoaded >= tilesLoading) {
          // All visible tiles loaded
          this.$emit('tiles-loaded')
        }
      })

      // Full screen handlers
      this.viewer.addHandler('full-screen', (event) => {
        this.isFullscreen = event.fullScreen
      })

      // Error handler
      this.viewer.addHandler('open-failed', (event) => {
        this.error = 'Failed to open slide: ' + event.message
        this.loading = false
      })
    },

    async loadSlide() {
      if (!this.slideInfo || !this.viewer) return

      try {
        this.loading = true
        this.error = null

        // Create custom tile source for SpinPath backend
        const tileSource = this.createTileSource()
        
        // Open the tile source in OpenSeadragon
        this.viewer.open(tileSource)
        
      } catch (error) {
        console.error('Error loading slide:', error)
        this.error = error.message || 'Failed to load slide'
      } finally {
        this.loading = false
      }
    },

    createTileSource() {
      // Create a custom tile source configuration for our backend
      const tileSource = {
        height: this.slideInfo.dimensions[1],
        width: this.slideInfo.dimensions[0],
        tileSize: this.slideInfo.tile_size[0],
        minLevel: 0,
        maxLevel: this.slideInfo.level_count - 1,
        
        // Custom tile URL function
        getTileUrl: (level, x, y) => {
          return `/api/slides/${this.slideId}/tile/${level}/${x}/${y}?format=JPEG&quality=85`
        },

        // Support for different levels with actual dimensions
        getLevelScale: (level) => {
          return 1.0 / this.slideInfo.level_downsamples[level]
        },

        // Get number of tiles for a level
        getNumTiles: (level) => {
          const levelDims = this.slideInfo.level_dimensions[level]
          const tileSize = this.slideInfo.tile_size[0]
          return {
            x: Math.ceil(levelDims[0] / tileSize),
            y: Math.ceil(levelDims[1] / tileSize)
          }
        },

        // Support for pixel density if available
        ...(this.slideInfo.mpp_x && {
          pixelDensityRatio: 1.0 / this.slideInfo.mpp_x
        })
      }

      return tileSource
    },

    // Control methods
    zoomIn() {
      if (this.viewer) {
        this.viewer.viewport.zoomBy(2)
      }
    },

    zoomOut() {
      if (this.viewer) {
        this.viewer.viewport.zoomBy(0.5)
      }
    },

    goHome() {
      if (this.viewer) {
        this.viewer.viewport.goHome()
      }
    },

    fullScreen() {
      if (this.viewer) {
        this.viewer.setFullScreen(!this.viewer.isFullScreen())
      }
    },

    changeLevel() {
      // For future implementation: level-specific viewing
      console.log('Changed to level:', this.selectedLevel)
    },

    toggleInfo() {
      this.showInfo = !this.showInfo
    },

    retryLoad() {
      this.initViewer()
    },

    // Utility methods
    formatFileSize(bytes) {
      if (!bytes) return 'Unknown'
      const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
      if (bytes === 0) return '0 Bytes'
      const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)))
      return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
    },

    cleanup() {
      if (this.viewer) {
        this.viewer.destroy()
        this.viewer = null
      }
    },

    // Public API methods for parent components
    getViewer() {
      return this.viewer
    },

    getSlideInfo() {
      return this.slideInfo
    },

    addAnnotation(annotation) {
      // For future implementation
      this.annotations.push(annotation)
    },

    removeAnnotation(id) {
      // For future implementation
      const index = this.annotations.findIndex(a => a.id === id)
      if (index !== -1) {
        this.annotations.splice(index, 1)
      }
    }
  }
}
</script>

<style scoped>
.image-viewer-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  overflow: hidden;
}

.viewer-controls {
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  z-index: 1000;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(0, 0, 0, 0.7);
  padding: 8px 12px;
  border-radius: 8px;
  backdrop-filter: blur(10px);
  flex-wrap: wrap;
  gap: 10px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-btn {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 14px;
  min-width: 40px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.control-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.5);
}

.level-select {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
  min-width: 150px;
}

.level-select option {
  background: #333;
  color: white;
}

.info-display {
  display: flex;
  gap: 15px;
  font-size: 12px;
}

.info-item {
  color: rgba(255, 255, 255, 0.9);
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  white-space: nowrap;
}

.zoom-info {
  font-weight: bold;
  color: #4CAF50;
}

.viewer-container {
  width: 100%;
  height: 100%;
  background: #000;
}

.viewer-container.fullscreen {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 9999 !important;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  color: white;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top: 3px solid #4CAF50;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-display {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(244, 67, 54, 0.9);
  color: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  z-index: 2000;
  max-width: 400px;
}

.retry-btn {
  background: white;
  color: #f44336;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 10px;
  font-weight: bold;
}

.info-panel {
  position: absolute;
  top: 70px;
  right: 10px;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  padding: 20px;
  border-radius: 8px;
  max-width: 300px;
  z-index: 1500;
  backdrop-filter: blur(10px);
}

.info-panel h3 {
  margin: 0 0 15px 0;
  color: #4CAF50;
  font-size: 16px;
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.info-row .label {
  font-weight: bold;
  color: rgba(255, 255, 255, 0.7);
  min-width: 80px;
}

.info-row .value {
  color: white;
  text-align: right;
}

.close-info-btn {
  background: #4CAF50;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 15px;
  width: 100%;
}

.minimap-container {
  position: absolute;
  bottom: 10px;
  right: 10px;
  width: 150px;
  height: 100px;
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  z-index: 1000;
}

.annotation-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 500;
}

/* Responsive design */
@media (max-width: 768px) {
  .viewer-controls {
    flex-direction: column;
    align-items: stretch;
  }
  
  .control-group {
    justify-content: center;
  }
  
  .info-display {
    flex-wrap: wrap;
    justify-content: center;
  }
  
  .info-panel {
    right: 5px;
    left: 5px;
    max-width: none;
  }
}
</style>
