# bAIsed Quick Reference Guide
## Google-Powered AI Fairness Workbench

### 🚀 Quick Start (30 seconds)

```bash
# 1. Start the server
python run.py

# 2. Open browser
http://localhost:5000/workbench

# 3. Click a demo button (💳 👔 🚔)

# 4. See results instantly
```

---

### 📊 Core Capabilities

#### **Fairness Metrics**
- DIR (Disparate Impact Ratio)
- SPD (Statistical Parity Difference)
- EOD (Equal Opportunity Difference)
- AOD (Average Odds Difference)
- Bias Score (0-100)

#### **Statistical Intelligence**
- Proxy Feature Detection (Cramer's V, Correlation)
- Dataset Risk Scoring (0-100)
- Bias Pattern Classification (7 types)
- Group hotspot detection

#### **AI & Simulation**
- What-If scenario testing
- Gemini-powered audit reports
- Colab notebook export
- What-If Tool export

---

### 🎯 Use Cases

| Use Case | Steps |
|----------|-------|
| **Quick Demo** | Click demo button (💳) → Review metrics |
| **Upload Data** | Upload CSV → Auto-detect columns → Analyze |
| **Explore Scenarios** | Change threshold → See impact on DIR/bias score |
| **Generate Report** | Click "AI Analyze" → Get Gemini report |
| **Further Analysis** | Export to Colab → Jupyter analysis |
| **TensorBoard** | Export to What-If Tool → Interactive visualization |

---

### 💡 Key Features

**Deterministic First**
- Reproducible results
- No ML model dependencies
- Easy to audit and explain

**Google Integrated**
- Gemini: AI-powered reports
- Colab: Notebook export
- What-If Tool: Interactive exploration

**End-to-End Flow**
- Demo datasets → Analysis → Export
- All in the browser workbench
- No manual configuration

---

### 📁 Project Files

```
Key files:
├── backend/
│   ├── proxy_detector.py       # Cramer's V + correlation
│   ├── risk_profiler.py        # 0-100 risk scoring
│   ├── pattern_detector.py     # 7 bias pattern types
│   ├── demo_datasets.py        # 3 demo types
│   ├── exporters.py            # Colab + What-If exports
│   └── api.py                  # All endpoints
├── frontend/
│   ├── pages/workbench.html    # Demo loader UI
│   └── js/workbench.js         # Demo handlers
├── demo_gdg.py                 # Presentation script
└── README.md                   # Full documentation
```

---

### 🔌 API Endpoints

```
GET  /api/demo-dataset/<type>          Get demo CSV
POST /upload                            Upload & analyze
POST /analyze                           Quick fairness check
POST /simulate                          What-if scenarios
POST /ai-analyze                        Gemini report
GET  /api/export/colab/<id>           Export to Colab
GET  /api/export/what-if/<id>         Export to What-If
```

---

### 🎬 Demo Script

```bash
# Run full GDG demo with colored output
python demo_gdg.py
```

Shows:
1. Load demo dataset
2. Upload & analyze
3. Proxy detection
4. Risk profiling
5. Pattern classification
6. What-if simulation
7. Gemini report
8. Export options

---

### 📋 Checklist for Presentation

- [ ] `python run.py` running
- [ ] Browser open to `http://localhost:5000/workbench`
- [ ] Click 💳 button and show instant analysis
- [ ] Scroll through metrics and patterns
- [ ] Show Gemini report
- [ ] Demo export buttons
- [ ] Optional: Run `python demo_gdg.py`

---

### 🔑 Environment Setup

```env
# .env file
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-1.5-flash
```

---

### 💬 Talking Points

1. **Problem**: Bias detection requires statistical knowledge
2. **Solution**: bAIsed automates it + AI explains it
3. **Innovation**: Proxy detection + pattern classification
4. **Integration**: Seamless Google Gemini + Colab + What-If
5. **Demo-Ready**: 3 pre-loaded bias examples

---

### ✅ Verification

```bash
# Quick test
curl http://localhost:5000/api/health
# Returns: {"message": "bAIsed API running"}

# Test demo dataset
curl http://localhost:5000/api/demo-dataset/credit | wc -l
# Should show ~2001 lines (2000 data + 1 header)
```

---

### 🎓 Key Takeaways

- ✅ Deterministic + Statistical fairness metrics
- ✅ Proxy feature detection with association scoring
- ✅ Gemini-powered insights
- ✅ Export to Google tools (Colab, What-If)
- ✅ Production-ready workbench
- ✅ Open source, MIT license

---

**Ready to demo! 🚀**

Questions? Check the full README.md or IMPLEMENTATION_COMPLETE.md
