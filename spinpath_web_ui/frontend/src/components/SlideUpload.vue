<template>
  <div class="slide-upload">
    <h2>Upload Slide</h2>
    <input type="file" @change="handleFileChange" ref="fileInput" />
    <button @click="uploadSlide" :disabled="!selectedFile || uploading">
      {{ uploading ? 'Uploading...' : 'Upload' }}
    </button>
    <p v-if="uploadMessage">{{ uploadMessage }}</p>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'SlideUpload',
  data() {
    return {
      selectedFile: null,
      uploading: false,
      uploadMessage: '',
    };
  },
  methods: {
    handleFileChange(event) {
      this.selectedFile = event.target.files[0];
      this.uploadMessage = ''; // Clear previous message
    },
    async uploadSlide() {
      if (!this.selectedFile) {
        this.uploadMessage = 'Please select a file first.';
        return;
      }

      this.uploading = true;
      this.uploadMessage = '';
      const formData = new FormData();
      formData.append('file', this.selectedFile);

      try {
        // Assuming the backend is running on http://localhost:8000
        // Adjust if your backend URL is different.
        const response = await axios.post('http://localhost:8000/slides', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
        this.uploadMessage = `Success: ${response.data.message} (ID: ${response.data.id})`;
        this.$refs.fileInput.value = null; // Reset file input
        this.selectedFile = null;
        this.$emit('upload-success'); // Emit event here
      } catch (error) {
        if (error.response) {
          this.uploadMessage = `Error: ${error.response.data.detail || 'Upload failed.'}`;
        } else if (error.request) {
          this.uploadMessage = 'Error: No response from server. Is the backend running?';
        } else {
          this.uploadMessage = `Error: ${error.message}`;
        }
      } finally {
        this.uploading = false;
      }
    },
  },
};
</script>

<style scoped>
.slide-upload {
  margin: 20px;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
}
input[type="file"] {
  margin-right: 10px;
}
</style>
