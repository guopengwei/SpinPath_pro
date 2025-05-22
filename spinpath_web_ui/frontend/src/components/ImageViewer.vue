<template>
  <div class="image-viewer-container">
    <div :id="viewerId" class="openseadragon-viewer"></div>
    <p v-if="slideId">Displaying viewer for Slide ID: {{ slideId }}</p>
    <p v-else>No slide selected for viewer.</p>
  </div>
</template>

<script>
import OpenSeadragon from 'openseadragon';

export default {
  name: 'ImageViewer',
  props: {
    slideId: {
      type: String,
      default: null,
    },
  },
  data() {
    return {
      viewer: null,
      viewerId: 'openseadragon-viewer-' + Math.random().toString(36).substring(7), // Unique ID for the viewer div
    };
  },
  watch: {
    slideId(newSlideId) {
      if (newSlideId) {
        this.initViewer(newSlideId);
      } else if (this.viewer) {
        this.viewer.destroy();
        this.viewer = null;
      }
    }
  },
  methods: {
    initViewer(slideIdToView) {
      if (this.viewer) {
        this.viewer.destroy();
      }

      // IMPORTANT: The backend tileSource endpoint currently returns JSON.
      // OpenSeadragon expects image tiles. This will likely result in errors
      // or a blank viewer. This is expected for this step.
      // We will adapt the backend or use a custom tile source later.
      // const tileSourceUrl = `http://localhost:8000/slides/${slideIdToView}/tile/`;

      this.viewer = OpenSeadragon({
        id: this.viewerId,
        prefixUrl: 'https://openseadragon.github.io/openseadragon/images/', // Default OSD images
        tileSources: {
          type: 'image', // This is a placeholder type. For DZI or custom, this would change.
                          // For now, we're pointing to a URL that should serve tiles.
                          // OpenSeadragon might try to append standard tile requests like /0/0_0.png
          url: `http://localhost:8000/slides/${slideIdToView}/tile_placeholder.jpg`, // Placeholder, will cause 404 or error.
                                                                                      // This needs to be a DZI file or a custom tile source.
          // For a custom tile source that matches our backend:
          // getTileUrl: function(level, x, y) {
          //    // Our backend has /level/z/x/y, OSD uses level, x, y. We need to map this.
          //    // Assuming 'z' can be defaulted or is part of 'level' logic.
          //    // For now, let's assume a simple mapping for z=0 or fixed.
          //    // THIS IS A SIMPLIFICATION AND WILL NEED REFINEMENT.
          //    return `${tileSourceUrl}${level}/0/${x}/${y}`;
          // }
          // Since our backend returns JSON for tiles now, let's use a more direct, albeit likely non-functional, approach for this step.
          // We will need a proper DZI or custom tile source for actual image display.
          // The line below is how one might structure it for a custom source, but it won't work with current backend.
          // For now, let's use a simple image type pointing to a non-existent DZI to see OSD initialize.
          // This will be replaced with a proper Deep Zoom Image (DZI) source or a custom tile source later.
          // For this step, we'll use a placeholder that OpenSeadragon can try to load.
          // A common test DZI is available, but let's stick to our backend structure for now,
          // acknowledging it won't display an image yet.
           levels: [/* mock levels if needed, or let OSD try to figure it out */],
           width: 8000, // Placeholder width
           height: 6000, // Placeholder height
           tileSize: 256,
           getTileUrl: function(level, x, y) {
               // This matches the backend's /slides/{slide_id}/tile/{level}/{z}/{x}/{y}
               // We'll use a fixed z=0 for now.
               // This will still fail to load an image because the backend returns JSON, not an image.
               // But it sets up the structure for future integration.
               return `http://localhost:8000/slides/${slideIdToView}/tile/${level}/0/${x}/${y}.png`; // Added .png for OSD to treat as image
           }
        },
        showNavigator: true,
      });

      this.viewer.addHandler('open-failed', (event) => {
        console.error('OpenSeadragon open-failed:', event);
        // This error is expected at this stage due to backend returning JSON.
      });
    },
  },
  mounted() {
    if (this.slideId) {
      this.initViewer(this.slideId);
    }
  },
  beforeUnmount() {
    if (this.viewer) {
      this.viewer.destroy();
    }
  },
};
</script>

<style scoped>
.image-viewer-container {
  margin: 20px;
  padding: 10px;
  border: 1px solid #ddd;
  background-color: #f0f0f0;
}
.openseadragon-viewer {
  width: 800px; /* Adjust as needed */
  height: 600px; /* Adjust as needed */
  background-color: #fff;
  border: 1px solid #aaa;
}
</style>
