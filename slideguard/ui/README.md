# SlideGuard UI

This module provides a Gradio-based web interface for SlideGuard, allowing users to upload PDF presentations, select evaluation criteria, and view results in an interactive format.

## Features

- **PDF Upload**: Upload presentation files in PDF format
- **Criteria Selection**: Choose which evaluation criteria to apply
- **Presentation Type Selection**: Filters available criteria and enables type-aware prompts
- **Criteria Language Selection**: Choose EN/RU for LLM output language independent of UI language
- **Deck-Level Results**: View overall presentation evaluation results
- **Interactive Presentation Viewer**: Navigate through slides with corresponding evaluations
- **PDF Report Generation**: Generate comprehensive PDF reports with all evaluation results for download

## Installation

Make sure you have the required dependencies installed:

```bash
# Install additional UI dependencies
pip install gradio PyMuPDF reportlab
```

Or if using Poetry:

```bash
poetry install
```

## Usage

### Running the UI

You can launch the UI in several ways:

1. **Using the launcher script**:
   ```bash
   python slideguard/ui/launch.py
   ```

2. **Direct execution**:
   ```bash
   python -m slideguard.ui.app
   ```

3. **From the project root**:
   ```bash
   python -c "from slideguard.ui.app import create_app; create_app().launch()"
   ```

4. **Via CLI**:
   ```bash
   slideguard ui run --lang en
   slideguard ui run --lang ru
   ```

### Configuration

Before using the UI, make sure you have configured your environment variables or `.env` file with the necessary API keys and settings. See the main SlideGuard documentation for configuration details.

### UI Components

1. **Upload Section**: Drag and drop or select a PDF file to upload
2. **Presentation Type**: Select the presentation type to filter available criteria
3. **Criteria Language**: Select EN/RU for evaluation output language
4. **Criteria Selection**: Check/uncheck the criteria you want to evaluate
5. **Results Tabs**:
   - **Interactive Presentation Viewer**: Navigate slides with evaluations (first tab)
   - **Deck-Level Results**: Overall presentation evaluation
6. **Report Generation**: Generate and download comprehensive PDF reports

### Navigation

In the Interactive Presentation Viewer:
- Use the "Previous" and "Next" buttons to navigate between slides
- The current slide number is displayed
- Slide evaluations appear below the slide image
- All slide images are extracted from the PDF for easy viewing

## Troubleshooting

### Common Issues

1. **"Evaluator not initialized"**: Check your configuration and API keys
2. **PDF processing errors**: Ensure the PDF file is valid and not corrupted
3. **Missing dependencies**: Install required packages with `pip install gradio PyMuPDF reportlab`
4. **Report generation fails**: Ensure you have run an evaluation before generating a report

### Debug Mode

The UI runs in debug mode by default, which provides detailed error messages and logging information.

## Development

To modify the UI:

1. Edit `slideguard/ui/app.py` for main UI logic
2. Update `slideguard/ui/launch.py` for launch configuration
3. Modify the UI layout and components as needed

The UI uses Gradio's Blocks interface for maximum flexibility in layout and functionality.
