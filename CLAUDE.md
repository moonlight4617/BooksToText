# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
- 日本語で返答してください
- 実装を進める際は./TODO.mdの内容を更新しながら進めてください

## Project Overview

This project is a Kindle book automation workflow that converts Kindle screenshot images to text using OCR analysis. The goal is to extract text from Japanese technical books (300-500 pages) for use with AI tools like NotebookLM.

## Project Status

Currently in early development phase:
- Requirements specification completed (`kindle_to_text_requirements.md`)
- Basic Node.js project structure initialized
- No implementation code yet

## Technical Architecture

### Target Workflow
1. **Image Collection**: Kindle app/device screenshots
2. **Preprocessing**: Image quality enhancement (noise reduction, contrast adjustment, rotation correction)
3. **OCR Processing**: Text extraction using Tesseract OCR or cloud APIs
4. **Postprocessing**: Text formatting, page combining, final output
5. **Quality Check**: Accuracy verification

### Technology Stack Decisions
- **Cost Constraint**: Must use free tools/services only
- **OCR Options**: Tesseract OCR (free), Google Cloud Vision API (1000 free/month), Azure Computer Vision (5000 free/month)
- **Languages**: Python (PIL/Pillow, pytesseract, OpenCV) or Node.js (jimp, node-tesseract-ocr)
- **Target**: 90% OCR accuracy for Japanese technical books

## Development Commands

The project currently has minimal package.json setup. Commands will be added as implementation progresses.

## Success Criteria
- Process 300-500 page technical books in 2-3 hours
- Achieve 90%+ character recognition rate
- Output text suitable for AI tool consumption
- Minimal manual intervention required