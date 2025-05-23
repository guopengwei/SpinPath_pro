# SpinPath Web UI

A modern web interface for the SpinPath whole slide image analysis toolkit. This application provides an intuitive way to upload histopathology slides, run deep learning inference, and visualize results.

## Features

- **Slide Management**: Upload, view, and manage whole slide images
- **Model Selection**: Choose from available pre-trained models (CTransPath, Phikon, etc.)
- **Real-time Inference**: Run inference jobs with progress tracking
- **Results Visualization**: View class predictions, attention maps, and patch information
- **Modern UI**: Responsive design with beautiful glassmorphism effects

## Architecture

The application consists of two main components:

### Backend (FastAPI)
- RESTful API for slide management and inference
- Integration with SpinPath library for actual ML inference
- Background job processing for long-running inference tasks
- CORS support for frontend communication

### Frontend (Vue.js 3)
- Modern single-page application
- Real-time updates with polling
- Responsive grid layout
- Modal-based image viewer

## Prerequisites

- Python 3.8+
- Node.js 16+
- Docker and Docker Compose (optional)

## Installation

### Option 1: Docker Compose (Recommended)

1. Clone the repository and navigate to the web UI directory:
```bash
cd spinpath_web_ui
```

2. Build and start the services:
```bash
docker-compose up --build
```

3. Access the application:
- Frontend: http://localhost:8080
- Backend API: http://localhost:8000

### Option 2: Manual Setup

#### Backend Setup

1. Navigate to the backend directory:
```bash
cd spinpath_web_ui/backend
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Start the FastAPI server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd spinpath_web_ui/frontend
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run serve
```

4. Access the frontend at http://localhost:8080

## Usage

### 1. Upload Slides

- Click the file input in the "Upload Slide" section
- Select a whole slide image file (supported formats: .svs, .tiff, .ndpi, etc.)
- Click "Upload" to upload the slide to the server

### 2. View Slides

- Uploaded slides appear in the "Uploaded Slides" section
- Each slide card shows filename, size, and upload date
- Click "View" to open the slide in the image viewer modal
- Click "Select for Inference" to add the slide to the inference queue

### 3. Run Inference

- Select a model from the dropdown in the "Run Inference" section
- Configure inference parameters:
  - Patch Size (μm): Size of patches extracted from the slide
  - Number of Workers: Parallel processing workers
- Selected slides appear as tags in the inference panel
- Click "Run Inference" to start the analysis

### 4. Monitor Progress

- Inference jobs show real-time status updates
- Progress bar indicates completion percentage
- Status indicators: PENDING → RUNNING → COMPLETED/FAILED

### 5. View Results

- Click "View Results" when inference is complete
- Results show class predictions with confidence scores
- Attention maps and patch information are available for detailed analysis
- Click "View Attention Map" to see attention weight statistics

## API Endpoints

### Slides
- `GET /slides` - List all uploaded slides
- `POST /slides` - Upload a new slide
- `GET /slides/{slide_id}` - Get slide metadata
- `DELETE /slides/{slide_id}` - Delete a slide

### Models
- `GET /models` - List available models

### Inference
- `POST /inference` - Create inference job
- `GET /inference/{job_id}` - Get job status
- `GET /inference/results/{job_id}` - Get inference results

### System
- `GET /` - API information
- `GET /health` - Health check

## Configuration

### Backend Configuration

The backend can be configured through environment variables:

- `SLIDES_BASE_DIR`: Directory for storing uploaded slides (default: "uploaded_slides")
- `PYTHONUNBUFFERED`: Set to 1 for immediate log output

### Frontend Configuration

Frontend configuration is handled through Vue.js environment variables and can be modified in the component files.

## Development

### Backend Development

The backend uses FastAPI with automatic API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Frontend Development

The frontend is built with Vue.js 3 and uses:
- Axios for HTTP requests
- Modern CSS with glassmorphism effects
- Responsive grid layouts
- Component-based architecture

### Adding New Models

To add support for new models:

1. Add the model configuration to `AVAILABLE_MODELS` in `backend/main.py`
2. Ensure the model is available in the SpinPath library
3. The model will automatically appear in the frontend dropdown

## Troubleshooting

### Common Issues

1. **Backend not starting**: Check that all Python dependencies are installed and SpinPath is available
2. **Frontend can't connect**: Ensure the backend is running on port 8000
3. **Inference fails**: Check that the selected model is properly configured in SpinPath
4. **File upload fails**: Verify the uploaded file is a valid slide format

### Logs

- Backend logs: Check the FastAPI server console output
- Frontend logs: Check the browser developer console
- Docker logs: `docker-compose logs -f`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is part of the SpinPath toolkit. Please refer to the main SpinPath repository for licensing information.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the API documentation at http://localhost:8000/docs
3. Open an issue in the main SpinPath repository 