<template>
  <div id="app">
    <img alt="Vue logo" src="./assets/logo.png">
    <h1>SpinPath Web UI</h1>
    <SlideUpload @upload-success="refreshSlideList" />
    <SlideList ref="slideListComponent" @slide-selected="viewSlide" />
    <ImageViewer :slide-id="currentSlideIdForViewer" />
    <InferencePanel />
    <ResultsDisplay /> 
  </div>
</template>

<script>
import SlideUpload from './components/SlideUpload.vue';
import SlideList from './components/SlideList.vue';
import ImageViewer from './components/ImageViewer.vue';
import InferencePanel from './components/InferencePanel.vue';
import ResultsDisplay from './components/ResultsDisplay.vue'; // Import ResultsDisplay

export default {
  name: 'App',
  components: {
    SlideUpload,
    SlideList,
    ImageViewer,
    InferencePanel,
    ResultsDisplay, // Register ResultsDisplay
  },
  data() {
    return {
      currentSlideIdForViewer: null,
    };
  },
  methods: {
    refreshSlideList() {
      this.$refs.slideListComponent.fetchSlides();
    },
    viewSlide(slideId) {
      this.currentSlideIdForViewer = slideId;
    }
  }
};
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
