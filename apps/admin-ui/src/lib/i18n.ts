import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const resources = {
  hu: {
    translation: {
      // Navigation
      dashboard: 'Áttekintés',
      entities: 'Entitások',
      clusters: 'Clusterek',
      maintenance: 'Karbantartás', 
      monitoring: 'Monitoring',
      
      // Dashboard
      systemOverview: 'Rendszer áttekintés',
      database: 'Adatbázis',
      schema: 'Séma',
      vector: 'Vektor',
      system: 'Rendszer',
      status: 'Állapot',
      current: 'Jelenlegi',
      latest: 'Legújabb',
      dimension: 'Dimenzió',
      ok: 'Rendben',
      error: 'Hiba',
      mismatch: 'Eltérés',
      degraded: 'Gyengített',
      
      // Entities
      search: 'Keresés',
      filters: 'Szűrők',
      displayed: 'Megjelenített',
      total: 'Összes',
      domainTypes: 'Domain típusok',
      areas: 'Területek',
      entityList: 'Entitások listája',
      clearFilters: 'Szűrők törlése',
      selectDomain: 'Domain kiválasztása',
      selectArea: 'Terület kiválasztása',
      allDomains: 'Minden domain',
      allAreas: 'Minden terület',
      attributes: 'Attribútumok',
      
      // Clusters
      clusterManagement: 'Cluster kezelés',
      addCluster: 'Cluster hozzáadása',
      editCluster: 'Cluster szerkesztése',
      deleteCluster: 'Cluster törlése',
      name: 'Név',
      type: 'Típus',
      scope: 'Hatókör',
      tags: 'Címkék',
      description: 'Leírás',
      actions: 'Műveletek',
      edit: 'Szerkesztés',
      delete: 'Törlés',
      save: 'Mentés',
      cancel: 'Mégse',
      create: 'Létrehozás',
      
      // Maintenance
      systemStatus: 'Rendszer állapot',
      available: 'Elérhető',
      unavailable: 'Nem elérhető',
      cpu: 'CPU',
      memory: 'Memória',
      usage: 'használat',
      databaseInit: 'Adatbázis inicializálás',
      cacheClear: 'Cache törlés',
      vectorReindex: 'Vektor újraindexelés',
      runBootstrap: 'Bootstrap futtatása',
      clearCache: 'Cache törlése',
      reindex: 'Újraindexelés',
      running: 'Futás',
      deleting: 'Törlés',
      indexing: 'Indexelés',
      systemInfo: 'Rendszer információk',
      serviceInfo: 'Szolgáltatás információk',
      databaseStats: 'Adatbázis statisztikák',
      lastOperation: 'Utolsó művelet eredménye',
      noLogs: 'Nincsenek logok',
      clear: 'Törlés',
      
      // Monitoring
      autoRefresh: 'Automatikus frissítés',
      responseTime: 'Válaszidő',
      average: 'átlag',
      serviceStatus: 'Szolgáltatás állapot',
      vectorSearch: 'Vektor keresés',
      vectorDimension: 'Vektor dimenzió',
      cpuMemoryUsage: 'CPU & Memória használat',
      systemLogs: 'Rendszer logok',
      allLevels: 'Összes szint',
      errorsOnly: 'Csak hibák',
      warnings: 'Figyelmeztetések',
      info: 'Információk',
      debug: 'Debug',
      dataCollection: 'Adatgyűjtés folyamatban',
      
      // Common
      loading: 'Betöltés',
      na: 'N/A',
      yes: 'Igen',
      no: 'Nem',
      home: 'Kezdőlap',
      settings: 'Beállítások',
      logout: 'Kijelentkezés',
      
      // Log levels
      logError: 'Hiba',
      logWarning: 'Figyelmeztetés',
      logInfo: 'Info',
      logDebug: 'Debug',
    }
  },
  en: {
    translation: {
      // Navigation
      dashboard: 'Dashboard',
      entities: 'Entities',
      clusters: 'Clusters',
      maintenance: 'Maintenance',
      monitoring: 'Monitoring',
      
      // Dashboard
      systemOverview: 'System Overview',
      database: 'Database',
      schema: 'Schema',
      vector: 'Vector',
      system: 'System',
      status: 'Status',
      current: 'Current',
      latest: 'Latest',
      dimension: 'Dimension',
      ok: 'OK',
      error: 'Error',
      mismatch: 'Mismatch',
      degraded: 'Degraded',
      
      // Entities
      search: 'Search',
      filters: 'Filters',
      displayed: 'Displayed',
      total: 'Total',
      domainTypes: 'Domain Types',
      areas: 'Areas',
      entityList: 'Entity List',
      clearFilters: 'Clear Filters',
      selectDomain: 'Select Domain',
      selectArea: 'Select Area',
      allDomains: 'All Domains',
      allAreas: 'All Areas',
      attributes: 'Attributes',
      
      // Clusters
      clusterManagement: 'Cluster Management',
      addCluster: 'Add Cluster',
      editCluster: 'Edit Cluster',
      deleteCluster: 'Delete Cluster',
      name: 'Name',
      type: 'Type',
      scope: 'Scope',
      tags: 'Tags',
      description: 'Description',
      actions: 'Actions',
      edit: 'Edit',
      delete: 'Delete',
      save: 'Save',
      cancel: 'Cancel',
      create: 'Create',
      
      // Maintenance
      systemStatus: 'System Status',
      available: 'Available',
      unavailable: 'Unavailable',
      cpu: 'CPU',
      memory: 'Memory',
      usage: 'usage',
      databaseInit: 'Database Initialization',
      cacheClear: 'Cache Clear',
      vectorReindex: 'Vector Reindex',
      runBootstrap: 'Run Bootstrap',
      clearCache: 'Clear Cache',
      reindex: 'Reindex',
      running: 'Running',
      deleting: 'Deleting',
      indexing: 'Indexing',
      systemInfo: 'System Information',
      serviceInfo: 'Service Information',
      databaseStats: 'Database Statistics',
      lastOperation: 'Last Operation Result',
      noLogs: 'No logs',
      clear: 'Clear',
      
      // Monitoring
      autoRefresh: 'Auto refresh',
      responseTime: 'Response Time',
      average: 'average',
      serviceStatus: 'Service Status',
      vectorSearch: 'Vector Search',
      vectorDimension: 'Vector Dimension',
      cpuMemoryUsage: 'CPU & Memory Usage',
      systemLogs: 'System Logs',
      allLevels: 'All Levels',
      errorsOnly: 'Errors Only',
      warnings: 'Warnings',
      info: 'Information',
      debug: 'Debug',
      dataCollection: 'Data collection in progress',
      
      // Common
      loading: 'Loading',
      na: 'N/A',
      yes: 'Yes',
      no: 'No',
      home: 'Home',
      settings: 'Settings',
      logout: 'Logout',
      
      // Log levels
      logError: 'Error',
      logWarning: 'Warning',
      logInfo: 'Info',
      logDebug: 'Debug',
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'hu', // Default to Hungarian
    debug: false,
    
    interpolation: {
      escapeValue: false,
    },
    
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  });

export default i18n;