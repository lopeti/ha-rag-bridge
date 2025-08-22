# HA-RAG-Bridge Biztonságos Refaktor Terv
**Létrehozva:** 2025-08-22  
**Állapot:** TERVEZÉS  
**Cél:** A backup branch jó struktúrájának biztonságos visszahozása

## 🎯 Célkitűzés

A `refactor-attempt-backup` branch-ben lévő jobb kódszervezést visszahozni, de ezúttal **incrementálisan, teszteléssel minden lépés után**, hogy elkerüljük az előző teljes összeomlást.

## 📊 Jelenlegi Helyzet (2025-08-22)

### ✅ **Működő Állapot**
- **Branch:** `main` (commit: d9da001 "backup: Save current state before project reorganization")
- **Admin UI:** ✅ Működik: `http://100.82.211.22:8000/admin/ui/settings`
- **API Endpoints:** ✅ `/admin/config`, `/admin/status`, stb.
- **Frontend:** ✅ Built in `apps/admin-ui/dist/`
- **Docker:** ✅ Containers futnak

### 🚨 **Backup Branch Struktúra** (refactor-attempt-backup)
```
ha-rag-bridge/
├── app/
│   ├── services/                 # 🎯 CÉLSTRUKTÚRA
│   │   ├── core/                # state_service, service_catalog
│   │   ├── rag/                 # entity_reranker, query_*, cluster_manager
│   │   ├── conversation/        # conversation_*, async_*
│   │   └── integrations/        # külső rendszerek
│   ├── langgraph_workflow/
│   ├── routers/
│   └── middleware/
├── frontend/admin-ui/            # 🎯 ÁTNEVEZÉS: apps/admin-ui → frontend/admin-ui
├── config/
│   ├── environments/            # 🎯 ÚJ: környezet-specifikus .env
│   └── litellm/
└── ha_rag_bridge/               # változatlan
```

## 🗂️ **Mi Ment Rosszul az Előző Refaktor Kísérletben?**

1. **Túl nagy batch változások** (50+ fájl egyszerre)
2. **API endpoint útvonalak törése** (admin UI nem találta meg a `/admin/config`-ot)
3. **Frontend build path zavar** (apps vs frontend könyvtár)
4. **Import útvonal törések** (circular dependencies)
5. **Docker mount pont problémák**
6. **Nincs migration stratégia** az API kliensekhez

## 🔧 **5 Fázisos Biztonságos Megközelítés**

---

## **📋 FÁZIS 1: Service Könyvtár Szervezés**
**Időtartam:** ~1-2 óra  
**Kockázat:** ALACSONY  

### **1.1 Könyvtárstruktúra létrehozása**
```bash
mkdir -p app/services/core
mkdir -p app/services/rag  
mkdir -p app/services/conversation
mkdir -p app/services/integrations
```

### **1.2 Core Services átszervezése**
**Mozgatandó fájlok:**
- `app/services/service_catalog.py` → `app/services/core/service_catalog.py`
- `app/services/state_service.py` → `app/services/core/state_service.py` 
- `app/services/workflow_tracer.py` → `app/services/core/workflow_tracer.py`

**⚠️ FIGYELEM:** A `core/` mappában is van service_catalog.py - ezt EGYESÍTENI kell!

### **1.3 RAG Services átszervezése**
**Mozgatandó fájlok:**
- `app/services/entity_reranker.py` → `app/services/rag/entity_reranker.py`
- `app/services/cluster_manager.py` → `app/services/rag/cluster_manager.py`
- `app/services/query_expander.py` → `app/services/rag/query_expander.py`
- `app/services/query_rewriter.py` → `app/services/rag/query_rewriter.py`
- `app/services/query_scope_detector.py` → `app/services/rag/query_scope_detector.py`
- `app/services/search_debugger.py` → `app/services/rag/search_debugger.py`

### **1.4 Conversation Services átszervezése**  
**Mozgatandó fájlok:**
- `app/services/conversation_analyzer.py` → `app/services/conversation/conversation_analyzer.py`
- `app/services/conversation_memory.py` → `app/services/conversation/conversation_memory.py`
- `app/services/conversation_summarizer.py` → `app/services/conversation/conversation_summarizer.py`
- `app/services/async_conversation_enricher.py` → `app/services/conversation/async_conversation_enricher.py`
- `app/services/async_summarizer.py` → `app/services/conversation/async_summarizer.py`
- `app/services/quick_pattern_analyzer.py` → `app/services/conversation/quick_pattern_analyzer.py`

### **1.5 Import Átállítási Stratégia**
**Fokozatos megközelítés:**
1. **Másolás** (nem mozgatás) - így mindkét hely működik
2. **Import alias** létrehozása átmeneti időre
3. **Tesztelés** minden lépés után
4. **Régi fájlok törlése** CSAK ha az új helyen minden működik

**Példa átmeneti import:**
```python
# main.py-ben átmeneti időre mindkét import
try:
    from app.services.core.service_catalog import ServiceCatalog
except ImportError:
    from app.services.service_catalog import ServiceCatalog  # fallback
```

### **1.6 Tesztelési Checklist Fázis 1 után**
- [ ] Admin UI betölt: `http://100.82.211.22:8000/admin/ui/settings`
- [ ] Config API működik: `curl http://100.82.211.22:8000/admin/config`
- [ ] Health check: `curl http://100.82.211.22:8000/health`
- [ ] MyPy validation: `mypy app/`
- [ ] Ruff check: `ruff check app/`
- [ ] Docker restart successful: `docker compose down && docker compose up -d`

---

## **📋 FÁZIS 2: Duplicate Cleanup & Import Normalizálás**
**Időtartam:** ~30 perc  
**Kockázat:** ALACSONY  

### **2.1 Duplicate fájlok kezelése**
**Problémás fájlok:**
- `app/services/service_catalog.py` vs `app/services/core/service_catalog.py` (24 vs 100+ lines)
- `app/services/workflow_tracer.py` vs `app/services/core/workflow_tracer.py`

**Megoldás:** Egyesítés + funkcionalitás validálás

### **2.2 Import path cleanup**
- Régi importok eltávolítása
- Relatív importok normalizálása
- Circular dependency check

### **2.3 Tesztelési Checklist Fázis 2 után**
- [ ] Ugyanazok a tesztek mint Fázis 1-nél
- [ ] Nincs import error a logokban
- [ ] Minden service elérhető

---

## **📋 FÁZIS 3: Config & Environment Szervezés**
**Időtartam:** ~45 perc  
**Kockázat:** KÖZEPES  

### **3.1 Config könyvtárstruktúra**
```bash
mkdir -p config/environments
mkdir -p config/litellm  
```

### **3.2 Environment fájlok szervezése**
**Jelenlegi káosz:**
- `.env` (main)
- `.env.embedding` 
- `.env.sample`
- `.env.home`
- stb.

**Cél struktúra:**
```
config/environments/
├── .env.development
├── .env.production  
├── .env.testing
└── .env.template
```

### **3.3 Docker compose frissítések**
- Mount pont frissítések
- Environment file referencias

### **3.4 Tesztelési Checklist Fázis 3 után**
- [ ] Environment variables betöltődnek
- [ ] Configuration szolgáltatások működnek
- [ ] Admin UI config page működik

---

## **📋 FÁZIS 4: Frontend Átszervezés** 
**Időtartam:** ~30 perc  
**Kockázat:** KÖZEPES (build path!)

### **4.1 Frontend mozgatás**
```bash
# CSAK akkor, ha minden más működik!
mv apps/admin-ui frontend/admin-ui
```

### **4.2 Docker & Build path frissítések**
**docker-compose.yml változtatások:**
```yaml
# ELŐTTE:
volumes:
  - ./apps/admin-ui/dist:/app/apps/admin-ui/dist

# UTÁNA:  
volumes:
  - ./frontend/admin-ui/dist:/app/frontend/admin-ui/dist
```

### **4.3 FastAPI static file serving**
**app/routers/ui.py frissítés:**
```python
# Path változtatás
static_dir = "/app/frontend/admin-ui/dist"  # régen: apps/admin-ui/dist
```

### **4.4 Build script frissítések**
- `package.json` build scripts
- CI/CD pipeline frissítések

### **4.5 Tesztelési Checklist Fázis 4 után**
- [ ] `cd frontend/admin-ui && npm run build` működik
- [ ] Static fájlok elérhetők
- [ ] Admin UI betölt új helyről
- [ ] CSS/JS assets betöltődnek

---

## **📋 FÁZIS 5: API Szervezés (Opcionális)**
**Időtartam:** ~1 óra  
**Kockázat:** MAGAS - CSAK HA SZÜKSÉGES!

### **5.1 API Versioning (ha szükséges)**
- `app/api/v1/endpoints/` struktúra
- Backward compatibility
- Router migration

### **5.2 FIGYELEM: Ez törte el az előző refaktort!**
**NE CSINÁLJUK, hacsak nem kritikus!**

---

## 🔐 **Biztonságos Megközelítés Kulcszabályai**

### **1. Incremental & Testelt**
- ✅ **Maximum 1-3 fájl mozgatása** egy lépésben
- ✅ **Teljes teszt minden lépés után**
- ✅ **Git commit minden working állapotban**

### **2. Fallback Stratégia**
- ✅ **Import alias-ok** átmeneti időre
- ✅ **Fájl másolás** mozgatás helyett początkowo
- ✅ **Docker volume backup** kritikus fájlokról

### **3. Teszt Protokoll**
```bash
# Minden lépés után:
curl -s http://100.82.211.22:8000/health                    # Health check
curl -s http://100.82.211.22:8000/admin/ui/settings         # Admin UI  
curl -s http://100.82.211.22:8000/admin/config | head -5    # Config API
docker compose down && docker compose up -d                 # Container restart
mypy app/ && ruff check app/                                # Code quality
```

### **4. Rollback Terv**
**Ha bármi elromlik:**
1. `git checkout HEAD~1` - vissza az előző working commitra  
2. `docker compose down && docker compose up -d` - container restart
3. **Probléma elemzés** mielőtt újra próbálnánk

---

## 🐛 **Technical Debt Discovered During Refactor**

### **Fixed Issues:**
- ✅ **Import path fixes:** LangGraph workflow imports updated to new service structure
- ✅ **Admin UI authentication:** X-Admin-Token header missing from axios API client  
- ✅ **EventSource authentication:** Query parameter tokens for streaming endpoints
- ✅ **Vector dimension mismatch:** EMBED_DIM 1536→768 for local backend consistency
- ✅ **Pipeline debugger authentication:** fetch() calls replaced with authenticated API calls
- ✅ **Docker environment variables:** EMBED_DIM properly set in containers

### **Ongoing Issues:**
- 🔄 **Search quality problem:** Cross-encoder reranker incorrectly prioritizes `sensor.mold_indicator` over `sensor.nappali_homerseklet` despite perfect vector search results
- 🔄 **Area detection confusion:** Entities have `area_name: None` but area info in text field - reranker logic needs review
- 🔄 **Score normalization:** Mixed BM25/cosine similarity scores in hybrid search (cosmetic issue)

### **Impact on Refactor:**
- **Positive:** Issues discovered and fixed incrementally without breaking the overall system
- **Lessons:** Technical debt repair can be done safely alongside refactor work
- **Next:** Focus on frontend reorganization (Fázis 4) while noting search quality for future improvement

---

## 📝 **Progress Tracking**

### **Állapot Követés:**
- [x] **Fázis 1:** Service szervezés ✅ **ALREADY DONE!**
- [x] **Fázis 2:** Duplicate cleanup ✅ **ALREADY DONE!**
- [x] **Fázis 3:** Config szervezés ✅ **COMPLETED!**
- [ ] **Fázis 4:** Frontend átszervezés
- [ ] **Fázis 5:** API szervezés (opcionális)

### **Working Commits:**
- `main`: d9da001 - Starting point (WORKING)
- `refactor-v2-safe-incremental`: 3b77a21 - Service organization + Config reorganization (WORKING)
- **Latest:** All environment config files organized in config/environments/

### **Critical Files to Watch:**
- `app/main.py` - Service imports
- `app/routers/ui.py` - Static file serving
- `docker-compose.yml` - Volume mounts
- `apps/admin-ui/dist/` → `frontend/admin-ui/dist/` - Build output

---

## 🎯 **Siker Kritériumok (Definition of Done)**

### **Minimálisan működnie KELL:**
- ✅ Admin UI betölt és működik teljes funkcionalitással
- ✅ Minden API endpoint válaszol (admin, health, config)  
- ✅ Docker containers indulnak és stabilak
- ✅ MyPy + Ruff validáció pass-ol
- ✅ Konfigurációs rendszer működik

### **Bonus célok:**
- 📁 Tiszta service szervezés (core/rag/conversation)
- ⚙️ Rendezett config management
- 🎨 Frontend új helyen (frontend/admin-ui)
- 📚 Frissített dokumentáció

---

## ⚠️ **KRITIKUS Leckék az Előző Kudarcból**

### **❌ Ne csináljuk:**
1. **Batch file mozgatás** - max 1-3 fájl egyszerre
2. **API path breaking changes** - backward compatibility!
3. **Frontend path változtatás** build teszt nélkül
4. **Import path törés** alias-ok nélkül
5. **Docker mount chaos** - volume path ellenőrzés

### **✅ Feltétlenül csináljuk:**
1. **Teszt minden egyes lépés után**
2. **Git commit minden working állapotban** 
3. **Import fallback-ek** átmeneti időre
4. **Container restart teszt** minden változás után
5. **Rollback plan** ha elromlik

---

## 🔄 **Státusz Frissítések**

**2025-08-22 10:00:** Terv létrehozva, backup branch elemezve, biztonságos approach megtervezve.  
**2025-08-22 10:40:** 🎉 **MAJOR DISCOVERY:** Fázis 1-2 már kész volt! Service szervezés működik!  
**2025-08-22 16:30:** ✅ **Fázis 3 COMPLETED:** Config environments organizálva config/environments/ könyvtárba  
**2025-08-22 18:00-20:30:** 🔧 **Technical debt:** LangGraph import fixes, admin UI authentication fixes, dimension mismatch fixes, pipeline debugger fixes  
**2025-08-22 20:30:** 📊 **Search quality issues:** Cross-encoder reranker hibás prioritást ad - vector search alapból jó eredményeket ad  
**Következő:** Fázis 4 - Frontend átszervezés

---

**💡 Megjegyzés:** Ez a terv egy living document - frissítjük ahogy haladunk, hogy mindig naprakész legyen a státusz és a leckék.