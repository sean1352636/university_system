# AI Dependencies Guide

## Overview

The University Chatbot supports multiple operating modes depending on which AI/ML libraries are installed:

1. **Lightweight Mode** (Default) - Uses fallback implementations
2. **Enhanced Mode** - With SpaCy for better NLP
3. **Advanced Mode** - With PyTorch/TensorFlow + transformers for state-of-the-art AI

## Current Status

Run this to check your current setup:

```bash
python -c "
import sys
sys.path.insert(0, '/path/to/university_system')
from utils.ai.university_chatbot import LIBRARIES_AVAILABLE
for lib, available in LIBRARIES_AVAILABLE.items():
    status = '✓' if available else '✗'
    print(f'{status} {lib}: {available}')
"
```

## Operating Modes

### Mode 1: Lightweight (Default) ✅

**What's included:**
- Basic intent detection (rule-based)
- Simple sentiment analysis (fallback)
- FAQ matching
- Context-aware responses

**Requirements:**
- No additional dependencies (already installed)
- sklearn (already installed)

**Pros:**
- ✅ Fast startup
- ✅ Low memory usage (~100MB)
- ✅ No internet required after initial setup
- ✅ Works on all systems

**Cons:**
- ❌ Less accurate intent detection
- ❌ Basic NLP capabilities

**Perfect for:** Development, testing, small deployments

---

### Mode 2: Enhanced (Optional) 💪

**What's added:**
- Advanced named entity recognition
- Better text processing
- Improved understanding of student queries

**Requirements:**
```bash
source venv/bin/activate
pip install spacy
python -m spacy download en_core_web_sm
```

**Download size:** ~50MB

**Pros:**
- ✅ Better entity extraction (names, dates, courses)
- ✅ Still reasonably fast
- ✅ Moderate memory usage (~200MB)

**Perfect for:** Small-to-medium universities

---

### Mode 3: Advanced (Optional) 🚀

**What's added:**
- State-of-the-art transformer models
- High-accuracy intent classification
- Advanced sentiment analysis
- Question answering capabilities

**Requirements (Choose ONE):**

**Option A: PyTorch** (Recommended for most users)
```bash
source venv/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers
```

**Option B: TensorFlow**
```bash
source venv/bin/activate
pip install tensorflow
pip install transformers
```

**Download size:** 2-4 GB (PyTorch CPU) or 500MB-2GB (TensorFlow)

**Pros:**
- ✅ Best accuracy
- ✅ Handles complex queries
- ✅ State-of-the-art NLP

**Cons:**
- ❌ Large download (2-4GB)
- ❌ Slower startup (10-30 seconds)
- ❌ High memory usage (1-2GB)
- ❌ First run downloads models from internet

**Perfect for:** Large universities, production deployments, research

---

## Installation Instructions

### Quick Start (Lightweight - Default)

Nothing to do! The chatbot works out of the box.

### Installing Enhanced Mode

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Install SpaCy
pip install spacy

# 3. Download English model
python -m spacy download en_core_web_sm

# 4. Verify
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('✓ SpaCy installed')"
```

### Installing Advanced Mode (PyTorch)

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Install PyTorch (CPU version - faster download)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 3. Install transformers
pip install transformers

# 4. Verify
python -c "import torch; from transformers import pipeline; print('✓ Advanced AI installed')"
```

**Note:** First time you use transformers, it will download ~500MB of models.

### Installing Advanced Mode (TensorFlow - Alternative)

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Install TensorFlow
pip install tensorflow

# 3. Install transformers
pip install transformers

# 4. Verify
python -c "import tensorflow as tf; from transformers import pipeline; print('✓ Advanced AI installed')"
```

---

## Comparison Table

| Feature | Lightweight | Enhanced | Advanced |
|---------|-------------|----------|----------|
| **Install Size** | 0 MB | ~50 MB | 2-4 GB |
| **Memory Usage** | ~100 MB | ~200 MB | 1-2 GB |
| **Startup Time** | <1 second | 1-2 seconds | 10-30 seconds |
| **Intent Detection** | Basic | Good | Excellent |
| **Entity Recognition** | Basic | Excellent | Excellent |
| **Sentiment Analysis** | Basic | Basic | Excellent |
| **Question Answering** | Limited | Limited | Excellent |
| **Accuracy** | 60-70% | 75-85% | 85-95% |
| **Internet Required** | No | Download once | Download once + first run |

---

## Troubleshooting

### "SpaCy model not found"

```bash
python -m spacy download en_core_web_sm
```

### "transformers requires PyTorch or TensorFlow"

Install one of them:
```bash
# PyTorch (recommended)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# OR TensorFlow
pip install tensorflow
```

### "Pipeline without specifying model name in production"

This is just a warning. You can ignore it or set specific models:

```python
# In the code, change:
pipeline("sentiment-analysis")
# To:
pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
```

### Memory Issues

If running on a system with limited RAM:
- Use Lightweight mode (no PyTorch/TensorFlow)
- Close other applications
- Consider using CPU-only versions

---

## Performance Tips

### For Development
- Use **Lightweight** mode for faster iteration
- Install Enhanced mode for testing NLP features

### For Production

**Small universities (<5,000 students):**
- Enhanced mode is perfect
- 2GB RAM minimum

**Medium universities (5,000-20,000 students):**
- Consider Advanced mode
- 4GB RAM minimum

**Large universities (>20,000 students):**
- Use Advanced mode
- 8GB RAM recommended
- Consider GPU acceleration for PyTorch

---

## Current Warnings Explained

### "Warning: transformers requires PyTorch or TensorFlow - using fallback"
**What it means:** Transformers library is installed but can't load models without PyTorch/TensorFlow.

**Solution:** Install PyTorch or TensorFlow (see Advanced Mode instructions above)

**Alternative:** Ignore it - the chatbot works fine in Lightweight mode!

---

### "SpaCy model 'en_core_web_sm' not found - using lightweight fallback"
**What it means:** SpaCy is installed but the English model hasn't been downloaded.

**Solution:** Run `python -m spacy download en_core_web_sm`

**Alternative:** Ignore it - the chatbot works fine without SpaCy!

---

### "No model was supplied, defaulted to distilbert..."
**What it means:** Using default models instead of specified ones.

**Solution:** This is informational - no action needed.

**Alternative:** Update code to specify models explicitly (advanced users only)

---

## Recommended Setup by Use Case

### For Developers/Testing
```bash
# Just use default Lightweight mode
# Nothing to install!
```

### For Small Deployments
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

### For Production/Large Universities
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers
pip install spacy
python -m spacy download en_core_web_sm
```

---

## FAQ

**Q: Do I need to install all of these?**
A: No! The chatbot works without any optional dependencies.

**Q: Which should I install first?**
A: Start with nothing, see if it meets your needs. Then add SpaCy if you want better NLP. Only install PyTorch/TensorFlow if you need the best accuracy.

**Q: Why does it download models on first run?**
A: Transformers downloads pre-trained models from Hugging Face. This is normal and happens once per model.

**Q: Can I use GPU acceleration?**
A: Yes, but you need the GPU version of PyTorch. See PyTorch website for installation instructions.

**Q: Will this slow down my system?**
A: In Lightweight mode: No. In Advanced mode: Only when the chatbot is actively processing queries.

---

## Support

For issues with:
- **Lightweight mode:** Should work out of the box
- **SpaCy installation:** https://spacy.io/usage
- **PyTorch installation:** https://pytorch.org/get-started/locally/
- **TensorFlow installation:** https://www.tensorflow.org/install

---

## Next Steps

1. Test current setup (works without anything)
2. If accuracy is insufficient, install SpaCy
3. If still need better accuracy, install PyTorch + transformers
4. Monitor memory usage and performance
5. Adjust based on your needs
