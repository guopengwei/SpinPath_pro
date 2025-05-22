<template>
  <div class="slide-list">
    <h2>Available Slides</h2>
    <button @click="fetchSlides" :disabled="loading">
      {{ loading ? 'Refreshing...' : 'Refresh List' }}
    </button>
    <ul v-if="slides.length > 0">
      <li v-for="slide in slides" :key="slide.id">
        <span>{{ slide.filename }} (ID: {{ slide.id }})</span>
        <div>
          <button @click="selectSlideForViewing(slide.id)">View</button>
          <button @click="deleteSlide(slide.id)" :disabled="deleting === slide.id">
            {{ deleting === slide.id ? 'Deleting...' : 'Delete' }}
          </button>
        </div>
      </li>
    </ul>
    <p v-else-if="!loading && !errorMessage">No slides uploaded yet.</p>
    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
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
      deleting: null, // Stores the id of the slide being deleted
      errorMessage: '',
    };
  },
  methods: {
    async fetchSlides() {
      this.loading = true;
      this.errorMessage = '';
      try {
        // Assuming backend is at http://localhost:8000
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
      this.deleting = slideId;
      this.errorMessage = '';
      try {
        // Assuming backend is at http://localhost:8000
        await axios.delete(`http://localhost:8000/slides/${slideId}`);
        // Refresh the list after successful deletion
        this.fetchSlides(); 
      } catch (error) {
        this.handleApiError(error, `Failed to delete slide ${slideId}.`);
      } finally {
        this.deleting = null;
      }
    },
    handleApiError(error, defaultMessage) {
      if (error.response) {
        this.errorMessage = `Error: ${error.response.data.detail || defaultMessage}`;
      } else if (error.request) {
        this.errorMessage = 'Error: No response from server. Is the backend running?';
      } else {
        this.errorMessage = `Error: ${error.message}`;
      }
    },
    selectSlideForViewing(slideId) {
      this.$emit('slide-selected', slideId);
    }
  },
  mounted() {
    this.fetchSlides(); // Fetch slides when the component is mounted
  },
};
</script>

<style scoped>
.slide-list {
  margin: 20px;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
}
ul {
  list-style-type: none;
  padding: 0;
}
li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid #eee;
}
li:last-child {
  border-bottom: none;
}
li div button { /* Target buttons within the div inside li for specific spacing */
  margin-left: 5px;
}
/* General button styling can remain or be adjusted if needed */
/* button {
  margin-left: 10px; 
} */
.error-message {
  color: red;
}
</style>
