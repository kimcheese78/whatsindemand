// App.js - WhatsInDemand Career Intelligence App

import React, { useState, useEffect, useRef, createContext, useContext, useCallback, useMemo } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import {
  ArrowRight, Search, ChevronDown, X, Filter,
  Zap, Layers, ExternalLink, Clock
} from 'lucide-react';
import api from './services/api';
import { Panel, Eyebrow, Stat, Pill, HeroNumber } from './components/ui';

const SCREEN_TO_PATH = {
  landing: '/',
  login: '/login',
  signup: '/signup',
  'forgot-password': '/forgot-password',
  'reset-password': '/reset-password',
  'verify-email': '/verify-email',
  'role-selection': '/start',
  'skills-input': '/skills-input',
  dashboard: '/dashboard',
  account: '/account',
  about: '/about',
  terms: '/terms',
  privacy: '/privacy',
  contact: '/contact',
};
const PATH_TO_SCREEN = Object.fromEntries(
  Object.entries(SCREEN_TO_PATH).map(([k, v]) => [v, k])
);



// ============================================
// CONTEXT - Single source of truth
// ============================================

const AppContext = createContext(null);

const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
};

// Single localStorage key for the slice of state that should survive refresh.
// Stored as one JSON object so we get one read on init and one write per change.
// Bump SESSION_KEY if the shape changes incompatibly.
const SESSION_KEY = 'wid_session_v1';
const readSession = () => {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
};
const writeSession = (patch) => {
  if (typeof window === 'undefined') return;
  try {
    const current = readSession();
    window.localStorage.setItem(SESSION_KEY, JSON.stringify({ ...current, ...patch }));
  } catch { /* quota exceeded — ignore */ }
};
const clearSession = () => {
  if (typeof window === 'undefined') return;
  try { window.localStorage.removeItem(SESSION_KEY); } catch { /* ignore */ }
};

const AppProvider = ({ children }) => {
  // Hydrate from localStorage so refresh on /dashboard, /skills-input, /account
  // restores position instead of bouncing to landing.
  const _persisted = readSession();
  // Navigation — seed from URL so refresh/deep-link lands on correct screen
  const [currentScreen, setCurrentScreen] = useState(
    () => PATH_TO_SCREEN[typeof window !== 'undefined' ? window.location.pathname : '/'] || 'landing'
  );
  
  // User & Auth
  const [user, setUser] = useState(null);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupFullName, setSignupFullName] = useState('');
  
  // Role Selection
  const [selectedRole, setSelectedRole] = useState(_persisted.selectedRole || '');
  const [roleSearchQuery, setRoleSearchQuery] = useState(_persisted.selectedRole || '');
  const [showRoleDropdown, setShowRoleDropdown] = useState(false);
  const [selectedSeniority, setSelectedSeniority] = useState(_persisted.selectedSeniority || 'All');
  const [selectedLocation, setSelectedLocation] = useState(_persisted.selectedLocation || ['All']);

  // Career preferences baseline — what the user picked at role-selection time.
  // Stays fixed even when dashboard filters mutate selectedSeniority/selectedLocation.
  const [baseSeniority, setBaseSeniority] = useState(_persisted.baseSeniority || _persisted.selectedSeniority || '');
  const [baseLocation, setBaseLocation] = useState(_persisted.baseLocation || _persisted.selectedLocation || ['All']);

  // Dashboard Filters (inside dashboard)
  const [industries, setIndustries] = useState([]);
  const [selectedIndustries, setSelectedIndustries] = useState(_persisted.selectedIndustries || ['All']);
  const [selectedCompanies, setSelectedCompanies] = useState(_persisted.selectedCompanies || ['All']);
  const [appliedSeniority, setAppliedSeniority] = useState(_persisted.appliedSeniority || 'All');
  const [appliedLocation, setAppliedLocation] = useState(_persisted.appliedLocation || ['All']);
  const [activeTab, setActiveTab] = useState(_persisted.activeTab || 'overview');

  // Data
  const [allRoles, setAllRoles] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [roleData, setRoleData] = useState(_persisted.roleData || null);
  const [alternativeRoles, setAlternativeRoles] = useState([]);

  // userSkills — persisted (legacy key migrated into the session blob).
  const [userSkills, setUserSkillsState] = useState(() => {
    if (Array.isArray(_persisted.userSkills)) return _persisted.userSkills;
    // One-time migration from the old standalone key.
    if (typeof window === 'undefined') return [];
    try {
      const raw = window.localStorage.getItem('userSkills');
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  });
  const setUserSkills = useCallback((next) => {
    setUserSkillsState(next);
    writeSession({ userSkills: next });
  }, []);
  
  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [initialLoading, setInitialLoading] = useState(true);

  useEffect(() => {
    console.log('selectedLocation changed:', selectedLocation);
  }, [selectedLocation]);

  // Mirror onboarding/dashboard state to localStorage so refresh restores
  // position. roleData can be large; if writing fails (quota), writeSession
  // silently no-ops and the user falls back to restoreLastSession on next login.
  useEffect(() => {
    writeSession({
      selectedRole,
      selectedSeniority,
      selectedLocation,
      selectedIndustries,
      selectedCompanies,
      appliedSeniority,
      appliedLocation,
      baseSeniority,
      baseLocation,
      activeTab,
      roleData,
    });
  }, [
    selectedRole, selectedSeniority, selectedLocation,
    selectedIndustries, selectedCompanies,
    appliedSeniority, appliedLocation,
    baseSeniority, baseLocation,
    activeTab, roleData,
  ]);

  // Constants
  const seniorities = [
    { id: 'All', label: 'All Levels', subtitle: 'Any experience' },
    { id: 'entry', label: 'Entry Level', subtitle: '0-2 years' },
    { id: 'mid', label: 'Mid Level', subtitle: '3-5 years' },
    { id: 'senior', label: 'Senior Level', subtitle: '5-10 years' },
    { id: 'lead', label: 'Lead/Principal', subtitle: '10+ years' },
  ];

  const [locations, setLocations] = useState([
    { value: 'All', label: 'All Locations' },
    { value: 'Remote', label: 'Remote' }
  ]);
  const [groupedLocations, setGroupedLocations] = useState([]);

  // ============================================
  // API FUNCTIONS (defined before effects)
  // ============================================

  const fetchRoles = useCallback(async () => {
    try {
      const data = await api.getAvailableRoles(3);
      setAllRoles(data.roles || []);
    } catch (err) {
      console.error('Failed to fetch roles:', err);
      setAllRoles([]);
    }
  }, []);

  const fetchLocations = useCallback(async () => {
    try {
      const data = await api.getLocations();
      if (data.success) {
        setGroupedLocations(data.locations || []);
        
        // Build flat list for simple dropdowns if needed
        const flatLocations = [
          { value: 'All', label: 'All Locations', isSpecial: true },
          { value: 'Remote', label: 'Remote', isSpecial: true },
        ];
        
        data.locations.forEach(region => {
          region.countries.forEach(country => {
            flatLocations.push({
              value: country.value,
              label: country.name,
              region: region.region,
              jobCount: country.job_count
            });
          });
        });
        
        setLocations(flatLocations);
      }
    } catch (err) {
      console.error('Failed to fetch locations:', err);
    }
  }, []);

  const fetchIndustries = useCallback(async () => {
    try {
      const data = await api.getIndustries();
      setIndustries(data.industries || []);
    } catch (err) {
      console.error('Failed to fetch industries:', err);
      setIndustries([]);
    }
  }, []);

  const fetchCompanies = useCallback(async () => {
    try {
      const data = await api.getCompanies();
      setCompanies(data.companies || []);
    } catch (err) {
      console.error('Failed to fetch companies:', err);
      setCompanies([]);
    }
  }, []);

  const restoreLastSession = useCallback(async () => {
    try {
      const data = await api.getLastSession();
      
      if (data.has_session && data.session) {
        const session = data.session;
        
        // Restore selections
        setSelectedRole(session.target_role || '');
        setRoleSearchQuery(session.target_role || '');
        setSelectedSeniority(session.seniority_level || '');
        
        // FIX: Properly handle location which may be array, string, or PostgreSQL array format
        const parseLocation = (loc) => {
          if (!loc) {
            return ['All'];
          }
          if (Array.isArray(loc)) {
            return loc;
          }
          if (typeof loc === 'string') {
            // Handle PostgreSQL array format: {Thailand, Mexico}
            if (loc.startsWith('{') && loc.endsWith('}')) {
              const inner = loc.slice(1, -1);
              if (!inner) return ['All'];
              return inner.split(',').map(s => s.trim()).filter(Boolean);
            }
            // Handle JSON string format: ["Thailand", "Mexico"]
            if (loc.startsWith('[')) {
              try {
                const parsed = JSON.parse(loc);
                return Array.isArray(parsed) ? parsed : [loc];
              } catch {
                return [loc];
              }
            }
            // Single string value
            return [loc];
          }
          return ['All'];
        };
        
        const parsedLocation = parseLocation(session.location);
        setSelectedLocation(parsedLocation);
        setBaseSeniority(session.seniority_level || '');
        setBaseLocation(parsedLocation);
        
        // If we have cached analysis data, use it
        if (session.analysis) {
          setRoleData(session.analysis);
          setCurrentScreen('dashboard');
          setAppliedSeniority(session.seniority_level || '');
          setAppliedLocation(parsedLocation);
          return true;
        }

        // No cached analysis — refetch silently and route to dashboard.
        if (session.target_role && session.seniority_level) {
          try {
            const fresh = await api.getRoleInsights(
              session.target_role,
              session.seniority_level,
              parsedLocation,
            );
            if (fresh && fresh.success) {
              setRoleData(fresh);
              setAppliedSeniority(session.seniority_level || '');
              setAppliedLocation(parsedLocation);
              setCurrentScreen('dashboard');
              return true;
            }
          } catch (err) {
            console.error('Failed to refetch role insights:', err);
          }
        }

        // Fallback: go to role selection with pre-filled values
        setCurrentScreen('role-selection');
        return true;
      }
    } catch (err) {
      console.error('Failed to restore session:', err);
    }
    return false;
  }, []);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const data = await api.getCurrentUser();
      setUser(data.user);

      const restored = await restoreLastSession();
      if (!restored) {
        // Logged-in member with no saved preferences — go pick a role.
        setCurrentScreen('role-selection');
      }
    } catch (err) {
      console.error('Failed to fetch user:', err);
      localStorage.removeItem('authToken');
    }
  }, [restoreLastSession]);

  const exploreRole = useCallback(async () => {
    if (!selectedRole || !selectedSeniority) {
      setError('Please select a role and experience level');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await api.getRoleInsights(
        selectedRole,
        selectedSeniority,
        selectedLocation,
        !selectedIndustries.includes('All') ? selectedIndustries : null,
        !selectedCompanies.includes('All') ? selectedCompanies.map(id => parseInt(id, 10)) : null
      );

      if (data.success) {
        setRoleData(data);
        setActiveTab('overview');
        setAppliedSeniority(selectedSeniority);
        setAppliedLocation(selectedLocation);
        setBaseSeniority(selectedSeniority);
        setBaseLocation(selectedLocation);
        // Skills are role-specific. Drop any held skills not present in the
        // new role's skill set so the user only confirms the overlap.
        const newRoleIds = new Set((data.skills || []).map(s => s.skill_id));
        setUserSkills((userSkills || []).filter(s => newRoleIds.has(s.skill_id)));
        // Always route through skills-input so users can confirm/edit their
        // gap mapping for the new role.
        setCurrentScreen('skills-input');

        // Save session if user is logged in
        if (user) {
          try {
            await api.saveSession(
              selectedRole,
              selectedSeniority,
              selectedLocation,
              data
            );
          } catch (saveErr) {
            console.error('Failed to save session:', saveErr);
          }
        }
      } else {
        setError(data.error || 'Failed to analyze role');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedRole, selectedSeniority, selectedLocation, selectedIndustries, selectedCompanies, user, userSkills, setUserSkills]);

  // FIX #2: New function to switch roles (used by AlternativesTab)
  const switchToRole = useCallback(async (roleTitle) => {
    setSelectedRole(roleTitle);
    setRoleSearchQuery(roleTitle);
    setLoading(true);
    setError(null);

    try {
      const data = await api.getRoleInsights(
        roleTitle,
        selectedSeniority,
        selectedLocation,
        !selectedIndustries.includes('All') ? selectedIndustries : null,
        !selectedCompanies.includes('All') ? selectedCompanies.map(id => parseInt(id, 10)) : null
      );

      if (data.success) {
        setRoleData(data);
        setActiveTab('overview');
        setAppliedSeniority(selectedSeniority);
        setAppliedLocation(selectedLocation);
        setBaseSeniority(selectedSeniority);
        setBaseLocation(selectedLocation);
        const newRoleIds = new Set((data.skills || []).map(s => s.skill_id));
        setUserSkills((userSkills || []).filter(s => newRoleIds.has(s.skill_id)));
        setCurrentScreen('skills-input');

        // Save session if user is logged in
        if (user) {
          try {
            await api.saveSession(
              roleTitle,
              selectedSeniority,
              selectedLocation,
              data
            );
          } catch (saveErr) {
            console.error('Failed to save session:', saveErr);
          }
        }
      } else {
        setError(data.error || 'Failed to analyze role');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedSeniority, selectedLocation, selectedIndustries, selectedCompanies, user, userSkills, setUserSkills]);

  const handleLogin = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.login(loginEmail, loginPassword);
      setUser(data.user);
      
      // Try to restore last session
      const hasSession = await restoreLastSession();
      
      if (!hasSession) {
        // No saved session, go to role selection
        setCurrentScreen('role-selection');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [loginEmail, loginPassword, restoreLastSession]);

  const handleSignup = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.signup(
        signupEmail,
        signupPassword,
        signupFullName,
        selectedRole,
        selectedSeniority,
        selectedLocation
      );

      setUser(data.user);
      await exploreRole();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [signupEmail, signupPassword, signupFullName, selectedRole, selectedSeniority, selectedLocation, exploreRole]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userSkills'); // legacy key
    clearSession();
    api.logout();
    setUser(null);
    setRoleData(null);
    setSelectedRole('');
    setRoleSearchQuery('');
    setSelectedSeniority('All');
    setSelectedLocation(['All']);
    setBaseSeniority('');
    setBaseLocation(['All']);
    setSelectedIndustries(['All']);
    setSelectedCompanies(['All']);
    setAppliedSeniority('All');
    setAppliedLocation(['All']);
    setActiveTab('overview');
    setUserSkillsState([]);
    setCurrentScreen('landing');
  }, []);

  // ============================================
  // EFFECTS
  // ============================================

  // Check auth on mount
  useEffect(() => {
    const init = async () => {
      const token = localStorage.getItem('authToken');
      if (token) {
        await fetchCurrentUser();
      }
      setInitialLoading(false);
    };
    init();
  }, [fetchCurrentUser]);

  // Fetch roles on mount
  useEffect(() => {
    fetchRoles();
  }, [fetchRoles]);

  // Fetch locations on mount
  useEffect(() => {
    fetchLocations();
  }, [fetchLocations]);

  // Fetch industries on mount
  useEffect(() => {
    fetchIndustries();
  }, [fetchIndustries]);

  // Fetch companies on mount
  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  const value = {
    // Navigation
    currentScreen,
    setCurrentScreen,
    
    // User & Auth
    user,
    setUser,
    loginEmail,
    setLoginEmail,
    loginPassword,
    setLoginPassword,
    signupEmail,
    setSignupEmail,
    signupPassword,
    setSignupPassword,
    signupFullName,
    setSignupFullName,
    handleLogin,
    handleSignup,
    handleLogout,
    restoreLastSession,
    
    // Role Selection
    selectedRole,
    setSelectedRole,
    roleSearchQuery,
    setRoleSearchQuery,
    showRoleDropdown,
    setShowRoleDropdown,
    selectedSeniority,
    setSelectedSeniority,
    selectedLocation,
    setSelectedLocation,
    baseSeniority,
    baseLocation,

    // Dashboard Filters
    selectedIndustries,
    setSelectedIndustries,
    selectedCompanies,
    setSelectedCompanies,
    appliedSeniority,
    setAppliedSeniority,
    appliedLocation,
    setAppliedLocation,
    activeTab,
    setActiveTab,
    
    // Data
    allRoles,
    companies,
    industries,
    roleData,
    setRoleData,
    alternativeRoles,
    seniorities,
    locations,
    groupedLocations,
    userSkills,
    setUserSkills,
    
    // UI State
    loading,
    setLoading,
    error,
    setError,
    initialLoading,
    
    // Actions
    exploreRole,
    switchToRole,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

// ============================================
// SHARED COMPONENTS
// ============================================

const NavBar = () => {
  const { user, handleLogout, setCurrentScreen } = useApp();
  
  return (
    <nav className="px-8 py-6 border-b border-line">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <button 
          onClick={() => setCurrentScreen('landing')}
          className="text-lg font-medium tracking-widest hover:text-ink-muted transition-colors"
        >
          WhatsInDemand
        </button>
        
        {user ? (
          <div className="flex items-center gap-6">
            <button
              onClick={() => setCurrentScreen('dashboard')}
              aria-label="Go to dashboard"
              className="flex items-center gap-2 px-2 py-1 -mx-2 -my-1 rounded hover:bg-white/5 transition-colors"
            >
              <div className="w-8 h-8 bg-white/10 rounded-full flex items-center justify-center">
                <span className="text-sm font-medium">
                  {user.full_name?.charAt(0) || user.email?.charAt(0) || 'U'}
                </span>
              </div>
              <span className="text-sm font-medium hidden sm:inline">
                {user.full_name?.split(' ')[0] || 'Account'}
              </span>
            </button>
            <button
              onClick={handleLogout}
              className="text-md font-medium hover:text-ink-muted transition-colors"
            >
              SIGN OUT
            </button>
          </div>
        ) : (
          <button
            onClick={() => setCurrentScreen('login')}
            className="text-md font-medium hover:text-ink-muted transition-colors"
          >
            SIGN IN
          </button>
        )}
      </div>
    </nav>
  );
};

const Footer = () => {
  const { setCurrentScreen } = useApp();
  return (
    <footer className="border-t border-line mt-auto">
      <div className="max-w-7xl mx-auto px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-ink-muted text-xs">
        <div>© {new Date().getFullYear()} WhatsInDemand. All rights reserved.</div>
        <div className="flex items-center gap-5">
          <button
            onClick={() => setCurrentScreen('about')}
            className="hover:text-white transition-colors"
          >
            About
          </button>
          <button
            onClick={() => setCurrentScreen('terms')}
            className="hover:text-white transition-colors"
          >
            Terms
          </button>
          <button
            onClick={() => setCurrentScreen('privacy')}
            className="hover:text-white transition-colors"
          >
            Privacy
          </button>
          <button
            onClick={() => setCurrentScreen('contact')}
            className="hover:text-white transition-colors"
          >
            Contact
          </button>
        </div>
      </div>
    </footer>
  );
};

const ErrorMessage = ({ error, onClose, onRetry, retryLabel = 'Try again' }) => {
  if (!error) return null;

  return (
    <div className="mb-4 p-4 bg-accent-down/20 border border-red-500 text-accent-down flex items-start gap-3">
      <div className="flex-1"><strong>Error:</strong> {error}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium underline hover:text-red-300 whitespace-nowrap"
        >
          {retryLabel}
        </button>
      )}
      <button
        onClick={onClose}
        className="text-accent-down hover:text-red-300 flex-shrink-0"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};

// ============================================
// MULTI-SELECT DROPDOWN
// ============================================
// Replace your MultiSelectDropdown with this simpler version
const MultiSelectDropdown = ({ 
  options, 
  selected, 
  onChange, 
  allLabel = 'All',
  getOptionLabel = (opt) => opt,
  getOptionValue = (opt) => opt 
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isAllSelected = selected.length === 0 || selected.includes('All');
  
  const handleToggle = (value) => {
    let newSelected;
    
    if (value === 'All') {
      newSelected = ['All'];
    } else {
      newSelected = selected.filter(s => s !== 'All');
      if (newSelected.includes(value)) {
        newSelected = newSelected.filter(s => s !== value);
      } else {
        newSelected = [...newSelected, value];
      }
      if (newSelected.length === 0) {
        newSelected = ['All'];
      }
    }
    
    onChange(newSelected); // Immediately notify parent
  };

  const getDisplayText = () => {
    if (isAllSelected) return allLabel;
    if (selected.length === 1) {
      const opt = options.find(o => getOptionValue(o) === selected[0]);
      return opt ? getOptionLabel(opt) : selected[0];
    }
    return `${selected.length} selected`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`px-4 py-2 bg-surface border text-white text-sm focus:outline-none cursor-pointer flex items-center gap-2 min-w-[160px] transition-colors ${
          isOpen ? 'border-white' : 'border-line-strong hover:border-white/40'
        }`}
      >
        <span className="flex-1 text-left truncate">{getDisplayText()}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-zinc-900 border border-line-strong z-30 shadow-xl max-h-72 overflow-y-auto">
          {/* All option */}
          <label className="flex items-center gap-3 px-4 py-3 hover:bg-surface cursor-pointer border-b border-line">
            <input
              type="checkbox"
              checked={isAllSelected}
              onChange={() => handleToggle('All')}
              className="w-4 h-4 accent-white"
            />
            <span className="text-sm font-medium">{allLabel}</span>
          </label>

          {/* Individual Options */}
          {options.map((option, idx) => {
            const value = getOptionValue(option);
            const label = getOptionLabel(option);
            const isChecked = selected.includes(value) && !isAllSelected;
            
            return (
              <label 
                key={idx} 
                className="flex items-center gap-3 px-4 py-3 hover:bg-surface cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => handleToggle(value)}
                  className="w-4 h-4 accent-white"
                />
                <span className="text-sm truncate">{label}</span>
              </label>
            );
          })}

          {options.length === 0 && (
            <div className="px-4 py-6 text-center text-ink-muted text-sm">
              No options available
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================
// GROUPED LOCATION DROPDOWN (Multi-Select with Regions)
// ============================================
const LocationDropdown = ({ value, onChange, className = '' }) => {
  const { groupedLocations } = useApp();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Ensure value is always an array
  const selected = Array.isArray(value) ? value : [value];

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isAllSelected = selected.includes('All');

  const getCountriesInRegion = (regionName) => {
    const region = groupedLocations.find(r => r.region === regionName);
    return region ? region.countries.map(c => c.value) : [];
  };

  const isRegionFullySelected = (regionName) => {
    if (isAllSelected) return false;
    const countries = getCountriesInRegion(regionName);
    return countries.length > 0 && countries.every(c => selected.includes(c));
  };

  const isRegionPartiallySelected = (regionName) => {
    if (isAllSelected) return false;
    const countries = getCountriesInRegion(regionName);
    const selectedCount = countries.filter(c => selected.includes(c)).length;
    return selectedCount > 0 && selectedCount < countries.length;
  };

  const updateSelection = (newSelected) => {
    onChange(newSelected.length === 0 ? ['All'] : newSelected);
  };

  const handleAllClick = () => {
    updateSelection(['All']);
  };

  const handleRegionClick = (regionName) => {
    const countries = getCountriesInRegion(regionName);
    let newSelected = isAllSelected ? [] : selected.filter(s => s !== 'All');

    if (isRegionFullySelected(regionName)) {
      newSelected = newSelected.filter(s => !countries.includes(s));
    } else {
      newSelected = [...new Set([...newSelected, ...countries])];
    }

    updateSelection(newSelected);
  };

  const handleCountryClick = (countryValue) => {
    let newSelected = isAllSelected ? [] : selected.filter(s => s !== 'All');

    if (newSelected.includes(countryValue)) {
      newSelected = newSelected.filter(s => s !== countryValue);
    } else {
      newSelected = [...newSelected, countryValue];
    }

    updateSelection(newSelected);
  };

  const getDisplayText = () => {
    if (selected.includes('All')) return 'All Locations';
    if (selected.length === 1) return selected[0];
    
    // Check if a full region is selected
    for (const region of groupedLocations) {
      const countries = region.countries.map(c => c.value);
      if (countries.length > 0 && 
          countries.every(c => selected.includes(c)) && 
          selected.every(c => countries.includes(c))) {
        return region.region;
      }
    }
    
    return `${selected.length} countries`;
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`px-4 py-2 bg-surface border text-white text-sm focus:outline-none cursor-pointer flex items-center gap-2 min-w-[160px] transition-colors ${
          isOpen ? 'border-white' : 'border-line-strong hover:border-white/40'
        }`}
      >
        <span className="flex-1 text-left truncate">{getDisplayText()}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-zinc-900 border border-line-strong z-30 shadow-xl max-h-[320px] overflow-y-auto">
          {/* All Locations */}
          <label className="flex items-center gap-3 px-4 py-3 hover:bg-surface cursor-pointer border-b border-line">
            <input
              type="checkbox"
              checked={isAllSelected}
              onChange={handleAllClick}
              className="w-4 h-4 accent-white"
            />
            <span className="text-sm font-medium">All Locations</span>
          </label>

          {/* Regions */}
          {groupedLocations.map((region) => (
            <div key={region.region}>
              <label className="flex items-center gap-3 px-4 py-2 bg-zinc-950 hover:bg-surface cursor-pointer sticky top-0">
                <input
                  type="checkbox"
                  checked={isRegionFullySelected(region.region)}
                  ref={(el) => {
                    if (el) el.indeterminate = isRegionPartiallySelected(region.region);
                  }}
                  onChange={() => handleRegionClick(region.region)}
                  className="w-4 h-4 accent-white"
                />
                <span className="text-xs font-medium text-ink-muted tracking-wider">
                  {region.region.toUpperCase()}
                </span>
              </label>
              
              {region.countries.map((country) => (
                <label
                  key={country.value}
                  className="flex items-center gap-3 px-4 py-2 pl-8 hover:bg-surface cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={!isAllSelected && selected.includes(country.value)}
                    onChange={() => handleCountryClick(country.value)}
                    className="w-4 h-4 accent-white"
                  />
                  <span className="text-sm">{country.name}</span>
                </label>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================
// SINGLE SELECT DROPDOWN
// ============================================
const SingleSelectDropdown = ({ 
  options, 
  value, 
  onChange, 
  getOptionLabel = (opt) => opt.label || opt,
  getOptionValue = (opt) => opt.value || opt.id || opt,
  placeholder = 'Select...'
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedOption = options.find(opt => getOptionValue(opt) === value);
  const displayText = selectedOption ? getOptionLabel(selectedOption) : placeholder;

  const handleSelect = (optionValue) => {
    onChange(optionValue);
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`px-4 py-2 bg-surface border text-white text-sm focus:outline-none cursor-pointer flex items-center gap-2 min-w-[140px] transition-colors ${
          isOpen ? 'border-white' : 'border-line-strong hover:border-white/40'
        }`}
      >
        <span className="flex-1 text-left truncate text-white">{displayText}</span>
        <ChevronDown className={`w-4 h-4 text-white transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-full min-w-[180px] bg-zinc-900 border border-line-strong z-30 shadow-xl max-h-64 overflow-y-auto">
          {options.map((option, idx) => {
            const optValue = getOptionValue(option);
            const optLabel = getOptionLabel(option);
            const isSelected = optValue === value;
            
            return (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelect(optValue)}
                className={`w-full px-4 py-2 text-left text-sm hover:bg-surface transition-colors flex items-center justify-between ${
                  isSelected ? 'bg-white/10 text-white' : 'text-white'
                }`}
              >
                <span>{optLabel}</span>
                {isSelected && <span className="text-xs text-ink-muted">✓</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ============================================
// GOOGLE SIGN-IN BUTTON (Fixed for FedCM)
// ============================================
const GoogleSignInButton = ({ onSuccess, onError, text = "Continue with Google" }) => {
  const hiddenButtonRef = useRef(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let scriptEl;

    const initGoogle = () => {
      if (!window.google?.accounts?.id || !hiddenButtonRef.current) return;

      window.google.accounts.id.initialize({
        client_id: process.env.REACT_APP_GOOGLE_CLIENT_ID,
        callback: async (response) => {
          setIsLoading(true);
          try {
            const data = await api.googleAuth(response.credential);
            onSuccess(data);
          } catch (err) {
            onError(err.message || 'Google sign-in failed');
          } finally {
            setIsLoading(false);
          }
        },
        ux_mode: 'popup',
        use_fedcm_for_prompt: false,
      });

      hiddenButtonRef.current.innerHTML = '';
      window.google.accounts.id.renderButton(hiddenButtonRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'rectangular',
        width: 300,
      });

      setIsReady(true);
    };

    const timer = setTimeout(() => {
      if (window.google?.accounts?.id) {
        initGoogle();
      } else {
        scriptEl = document.createElement('script');
        scriptEl.src = 'https://accounts.google.com/gsi/client';
        scriptEl.async = true;
        scriptEl.defer = true;
        scriptEl.onload = initGoogle;
        document.body.appendChild(scriptEl);
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [onSuccess, onError]);

  const handleClick = () => {
    if (!hiddenButtonRef.current) return;
    const realButton = hiddenButtonRef.current.querySelector('div[role=button]')
      || hiddenButtonRef.current.querySelector('[role=button]')
      || hiddenButtonRef.current.querySelector('button');
    if (realButton) realButton.click();
  };

  if (isLoading) {
    return (
      <div
        className="w-full bg-white text-[#1f1f1f] flex items-center justify-center gap-3 border border-[#dadce0]"
        style={{
          height: '44px',
          fontFamily: 'Roboto, "Helvetica Neue", Arial, sans-serif',
          fontWeight: 500,
          fontSize: 14,
          letterSpacing: 0.25,
        }}
      >
        <DotSpinner size={18} tone="black" />
        Signing in…
      </div>
    );
  }

  return (
    <>
      <div
        ref={hiddenButtonRef}
        style={{ position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none', overflow: 'hidden', clip: 'rect(0 0 0 0)' }}
        aria-hidden="true"
      />
      <button
        type="button"
        onClick={handleClick}
        disabled={!isReady}
        className="w-full flex items-center justify-center gap-3 bg-white text-[#1f1f1f] border border-[#dadce0] hover:bg-[#f8f9fa] active:bg-[#f1f3f4] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        style={{
          height: '44px',
          paddingLeft: 12,
          paddingRight: 12,
          fontFamily: 'Roboto, "Helvetica Neue", Arial, sans-serif',
          fontWeight: 500,
          fontSize: 14,
          letterSpacing: 0.25,
        }}
      >
        <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          <path fill="none" d="M0 0h48v48H0z"/>
        </svg>
        <span>{text}</span>
      </button>
    </>
  );
};

// ============================================
// NO RESULTS MESSAGE
// ============================================

const NoResultsMessage = ({ onClearFilters, loading }) => (
  <div className="p-12 bg-surface border border-line text-center">
    <div className="text-5xl mb-4">🔍</div>
    <h3 className="text-2xl font-semibold mb-2">No Jobs Found</h3>
    <p className="text-ink-muted mb-6 max-w-md mx-auto">
      No jobs match your current filter combination. Try adjusting your filters or clearing them to see all results.
    </p>
    <button
      onClick={onClearFilters}
      disabled={loading}
      className={`px-6 py-3 font-medium transition-colors ${
        loading
          ? 'bg-white/20 text-ink-muted cursor-not-allowed'
          : 'bg-white text-black hover:bg-gray-200'
      }`}
    >
      {loading ? 'Loading...' : 'Clear All Filters'}
    </button>
  </div>
);

// ============================================
// LANDING SCREEN
// ============================================
const LandingScreen = () => {
  const { setCurrentScreen } = useApp();
  
  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />

      <div className="flex-1">
        <div className="max-w-4xl mx-auto px-6 sm:px-8 pt-20 sm:pt-32 pb-32">
          <h1 className="text-5xl sm:text-7xl md:text-8xl font-semibold mb-8 sm:mb-12 leading-none tracking-tight">
            YOUR ROLE <br />
            IS CHANGING
          </h1>

          <p className="text-lg sm:text-xl text-ink-muted mb-6 max-w-2xl leading-relaxed">
            AI is reshaping every profession. <br className="hidden sm:block" /> 
            Some skills are fading, while others are exploding in demand.
          </p>

          <p className="text-lg sm:text-xl text-ink-muted mb-6 max-w-2xl leading-relaxed" style={{ textWrap: 'balance' }}>
            We track thousands of job postings in real time to show you what's in demand, what's fading, and where to focus next.
          </p>
            
          <p className="text-lg sm:text-xl text-ink-muted mb-8 sm:mb-12 max-w-2xl leading-relaxed">
            No hype. Just data.
          </p>

          <div className="inline-flex flex-col items-start gap-3">
            <button 
              onClick={() => setCurrentScreen('role-selection')}
              className="px-8 sm:px-12 py-4 bg-white text-black font-medium text-lg sm:text-xl hover:bg-gray-200 transition-colors"
            >
              EXPLORE MY ROLE
            </button>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
};

// ============================================
// LOGIN SCREEN
// ============================================
const LoginScreen = () => {
  const { 
    loginEmail, 
    setLoginEmail, 
    loginPassword, 
    setLoginPassword,
    loading,
    error,
    setError,
    handleLogin,
    setCurrentScreen,
    setUser,
    restoreLastSession
  } = useApp();

  const onSubmit = (e) => {
    e.preventDefault();
    handleLogin();
  };

  const handleGoogleSuccess = async (data) => {
    setUser(data.user);
    const hasSession = await restoreLastSession();
    if (!hasSession) {
      setCurrentScreen('role-selection');
    }
  };

  const handleGoogleError = (errorMessage) => {
    setError(errorMessage);
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />

      <div className="flex-1">
        <div className="max-w-md mx-auto px-6 pt-16 pb-24">
          <div className="mb-6">
            <h1 className="text-4xl font-semibold mb-3 tracking-tight">
              SIGN IN
            </h1>
            <p className="text-ink-muted text-sm">
              Welcome back.
            </p>
          </div>

          <ErrorMessage error={error} onClose={() => setError(null)} />

          {/* Google Sign-In Button */}
          <GoogleSignInButton
            onSuccess={handleGoogleSuccess}
            onError={handleGoogleError}
          />

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-line-strong"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-black text-ink-muted uppercase tracking-wider">Or continue with email</span>
            </div>
          </div>

          <form onSubmit={onSubmit}>
            <div className="space-y-3 mb-6">
              <input
                type="email"
                placeholder="Email address"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="email"
              />
              <input
                type="password"
                placeholder="Password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="current-password"
              />
            </div>

            <div className="text-right mb-3 -mt-3">
              <button
                type="button"
                onClick={() => setCurrentScreen('forgot-password')}
                className="text-xs text-ink-muted hover:text-white transition-colors"
              >
                Forgot password?
              </button>
            </div>

            <button
              type="submit"
              disabled={loading || !loginEmail || !loginPassword}
              className={`w-full py-3 font-medium text-sm tracking-wide transition-colors ${
                !loading && loginEmail && loginPassword
                  ? 'bg-white text-black hover:bg-gray-200'
                  : 'bg-white/10 text-ink-faint cursor-not-allowed'
              }`}
            >
              {loading ? 'SIGNING IN...' : 'SIGN IN'}
            </button>
          </form>

          <div className="text-center text-ink-muted text-sm mt-6">
            Don't have an account?{' '}
            <button
              onClick={() => setCurrentScreen('signup')}
              className="text-white underline hover:text-ink"
            >
              Get started
            </button>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
};

// ============================================
// ROLE SELECTION SCREEN
// ============================================
const RoleSelectionScreen = () => {
  const { 
    selectedRole,
    setSelectedRole,
    roleSearchQuery,
    setRoleSearchQuery,
    showRoleDropdown,
    setShowRoleDropdown,
    selectedSeniority,
    setSelectedSeniority,
    selectedLocation,
    setSelectedLocation,
    allRoles,
    seniorities,
    locations,
    loading,
    error,
    setError,
    setCurrentScreen,
    user,
    exploreRole
  } = useApp();

  const dropdownRef = useRef(null);

  const filteredRoles = allRoles.filter(role => {
    const title = role.title || role;
    return title.toLowerCase().includes(roleSearchQuery.toLowerCase());
  });

  const handleRoleSelect = (role) => {
    const roleTitle = role.title || role;
    setSelectedRole(roleTitle);
    setRoleSearchQuery(roleTitle);
    setShowRoleDropdown(false);
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowRoleDropdown(false);
      }
    };

    if (showRoleDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showRoleDropdown, setShowRoleDropdown]);

  const canProceed = selectedRole && selectedSeniority;

  const handleExplore = async () => {
    if (!user) {
      // Go to signup first
      setCurrentScreen('signup');
    } else {
      await exploreRole();
    }
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />
  
      <div className="flex-1">
        <div className="max-w-3xl mx-auto px-8 pt-16 pb-24">
          <div className="mb-10">
            <h1 className="text-5xl md:text-6xl font-semibold mb-6 tracking-tight">
              WHAT'S YOUR ROLE?
            </h1>
            <p className="text-xl text-ink-muted">
              See what skills are in demand and how the role is evolving.
            </p>
          </div>

          <ErrorMessage
            error={error}
            onClose={() => setError(null)}
            onRetry={selectedRole && selectedSeniority && !loading ? handleExplore : null}
          />

          {/* Role Search */}
          <div className="mb-6">
            <label className="block text-sm text-ink-muted mb-2 tracking-wider font-medium">
              ROLE TITLE
            </label>
            <div className="relative" ref={dropdownRef}>
              <Search className="absolute left-5 top-1/2 transform -translate-y-1/2 w-5 h-5 text-ink-muted pointer-events-none" />
              <input
                type="text"
                value={roleSearchQuery}
                onChange={(e) => {
                  setRoleSearchQuery(e.target.value);
                  setShowRoleDropdown(true);
                  if (selectedRole && e.target.value !== selectedRole) {
                    setSelectedRole('');
                  }
                }}
                onFocus={() => {
                  if (!selectedRole) {
                    setShowRoleDropdown(true);
                  }
                }}
                onKeyDown={(e) => {
                  if (selectedRole && (e.key === 'Backspace' || e.key === 'Delete')) {
                    e.preventDefault();
                    setSelectedRole('');
                    setRoleSearchQuery('');
                    setShowRoleDropdown(false);
                  }
                }}
                placeholder={selectedRole ? '' : 'Search roles (e.g., Product Manager, Software Engineer)'}
                className={`w-full pl-14 pr-12 py-5 bg-surface border-2 text-white placeholder-gray-500 text-lg focus:outline-none transition-colors ${
                  selectedRole 
                    ? 'border-white bg-white/10' 
                    : 'border-line-strong focus:border-white'
                }`}
                readOnly={!!selectedRole}
              />
              
              {/* Show clear button when role is selected */}
              {selectedRole ? (
                <button
                  onClick={() => {
                    setSelectedRole('');
                    setRoleSearchQuery('');
                    setShowRoleDropdown(false);
                  }}
                  className="absolute right-5 top-1/2 transform -translate-y-1/2 text-ink-muted hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              ) : (
                <ChevronDown className={`absolute right-5 top-1/2 transform -translate-y-1/2 w-5 h-5 text-ink-muted pointer-events-none transition-transform ${showRoleDropdown ? 'rotate-180' : ''}`} />
              )}

              {/* Dropdown - only show when no role selected */}
              {showRoleDropdown && filteredRoles.length > 0 && !selectedRole && (
                <div className="absolute w-full mt-2 bg-zinc-900 border-2 border-line-strong max-h-72 overflow-y-auto z-20">
                  {filteredRoles.slice(0, 12).map((role, idx) => {
                    const roleTitle = role.title || role;
                    const jobCount = role.job_count;
                    return (
                      <button
                        key={idx}
                        onClick={() => handleRoleSelect(role)}
                        className="w-full px-5 py-4 text-left hover:bg-white/10 transition-colors border-b border-white/5 last:border-b-0 flex items-center justify-between"
                      >
                        <span className="text-base">{roleTitle}</span>
                        {jobCount && (
                          <span className="text-sm text-ink-muted">{jobCount} jobs</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            
            {/* Helper text when role is selected */}
            {selectedRole && (
              <div className="mt-2 text-sm text-ink-muted">
                Click the X to change your selection
              </div>
            )}
          </div>

          {/* Seniority Selection */}
          <div className="mb-6">
            <label className="block text-sm text-ink-muted mb-2 tracking-wider font-medium">
              EXPERIENCE LEVEL
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {seniorities.map((level) => (
                <button
                  key={level.id}
                  onClick={() => setSelectedSeniority(level.id)}
                  className={`p-4 text-left border-2 transition-all ${
                    selectedSeniority === level.id
                      ? 'border-white bg-white/10'
                      : 'border-line-strong hover:border-white/40'
                  }`}
                >
                  <div className="font-medium text-sm">{level.label}</div>
                  <div className="text-xs text-ink-muted">{level.subtitle}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Location Selection */}
          <div className="mb-10">
            <label className="block text-sm text-ink-muted mb-2 tracking-wider font-medium">
              LOCATION <span className="text-ink-faint"></span>
            </label>
            <LocationDropdown
              value={selectedLocation}
              onChange={setSelectedLocation}
              className="w-full"
            />
          </div>

          {/* CTA Button */}
          <button
            onClick={handleExplore}
            disabled={!canProceed || loading}
            className={`w-full py-5 font-medium text-xl transition-colors flex items-center justify-center gap-3 ${
              canProceed && !loading
                ? 'bg-white text-black hover:bg-gray-200'
                : 'bg-white/10 text-ink-faint cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <DotSpinner size={20} tone="white" />
                ANALYZING...
              </>
            ) : (
              <>
                EXPLORE THIS ROLE
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>

          <p className="text-center text-ink-muted text-sm mt-4">
            Free to explore (Beta)
          </p>

          <div className="flex justify-start pt-4">
            <button
              onClick={() => setCurrentScreen('landing')}
              className="text-small text-ink-muted hover:text-white transition-colors flex items-center gap-2"
            >
              ← Back
            </button>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
};

// ============================================
// SIGNUP SCREEN
// ============================================
const SignupScreen = () => {
  const { 
    signupFullName, 
    setSignupFullName,
    signupEmail, 
    setSignupEmail,
    signupPassword, 
    setSignupPassword,
    selectedRole,
    selectedSeniority,
    seniorities,
    loading,
    error,
    setError,
    handleSignup,
    setCurrentScreen,
    setUser,
    exploreRole
  } = useApp();

  const onSubmit = (e) => {
    e.preventDefault();
    handleSignup();
  };

  const handleGoogleSuccess = async (data) => {
    setUser(data.user);
    if (selectedRole && selectedSeniority) {
      await exploreRole();
    } else {
      setCurrentScreen('role-selection');
    }
  };

  const handleGoogleError = (errorMessage) => {
    setError(errorMessage);
  };

  const seniorityLabel = seniorities.find(s => s.id === selectedSeniority)?.label || '';

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />

      <div className="flex-1">
        <div className="max-w-md mx-auto px-6 pt-16 pb-24">
          <div className="mb-6">
            <h1 className="text-4xl font-semibold mb-3 tracking-tight">
              CREATE ACCOUNT
            </h1>
            <p className="text-ink-muted text-sm">
              Sign up to explore <span className="text-white font-semibold">{selectedRole}</span>
              {seniorityLabel && <span className="text-ink-muted"> • {seniorityLabel}</span>}
            </p>
          </div>

          <ErrorMessage error={error} onClose={() => setError(null)} />

          {/* Google Sign-In Button */}
          <GoogleSignInButton
            onSuccess={handleGoogleSuccess}
            onError={handleGoogleError}
            text="SIGN UP WITH GOOGLE"
          />

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-line-strong"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-black text-ink-muted uppercase tracking-wider">Or continue with email</span>
            </div>
          </div>

          <form onSubmit={onSubmit}>
            <div className="space-y-3 mb-4">
              <input
                type="text"
                placeholder="Full name"
                value={signupFullName}
                onChange={(e) => setSignupFullName(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="name"
              />
              <input
                type="email"
                placeholder="Email address"
                value={signupEmail}
                onChange={(e) => setSignupEmail(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="email"
              />
              <input
                type="password"
                placeholder="Password (min 8 characters)"
                value={signupPassword}
                onChange={(e) => setSignupPassword(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="new-password"
              />
            </div>

            <div className="mb-5 p-3 bg-surface border-l-2 border-white/40">
              <p className="text-xs text-ink-muted">
                By signing up, you agree to our{' '}
                <a href="#" className="text-white underline hover:text-ink">Terms of Service</a>
                {' '}and{' '}
                <a href="#" className="text-white underline hover:text-ink">Privacy Policy</a>
              </p>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setCurrentScreen('role-selection')}
                className="px-5 py-3 border border-line-strong text-sm font-medium hover:bg-surface transition-colors"
              >
                BACK
              </button>
              <button
                type="submit"
                disabled={loading || !signupEmail || !signupPassword || !signupFullName}
                className={`flex-1 py-3 font-medium text-sm tracking-wide transition-colors ${
                  !loading && signupEmail && signupPassword && signupFullName
                    ? 'bg-white text-black hover:bg-gray-200'
                    : 'bg-white/10 text-ink-faint cursor-not-allowed'
                }`}
              >
                {loading ? 'CREATING ACCOUNT...' : 'CREATE ACCOUNT'}
              </button>
            </div>
          </form>

          <div className="text-center text-ink-muted text-sm mt-6">
            Already have an account?{' '}
            <button 
              onClick={() => setCurrentScreen('login')}
              className="text-white underline hover:text-ink"
            >
              Sign in
            </button>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
};

// ============================================
// MOBILE HEADER
// ============================================

const MobileHeader = () => {
  const { 
    user,
    activeTab, 
    setActiveTab, 
    setCurrentScreen, 
    handleLogout 
  } = useApp();
  
  const [menuOpen, setMenuOpen] = useState(false);

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'employers', label: 'Companies' },
    { id: 'skills', label: 'Skills' },
    { id: 'paths', label: 'Paths' },
  ];

  return (
    <div className="lg:hidden">
      {/* Top Bar */}
      <div className="flex items-center justify-between p-4 border-b border-line bg-zinc-950">
        <button 
          onClick={() => setCurrentScreen('landing')}
          className="text-sm font-medium tracking-widest"
        >
          WhatsInDemand
        </button>
        
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="p-2 hover:bg-white/10 transition-colors"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Layers className="w-5 h-5" />}
        </button>
      </div>

      {/* Tab Bar */}
      <div className="flex border-b border-line bg-zinc-950 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 min-w-max px-4 py-3 text-xs font-medium tracking-wider transition-colors ${
              activeTab === tab.id
                ? 'text-white border-b-2 border-white'
                : 'text-ink-muted'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Dropdown Menu */}
      {menuOpen && (
        <div className="absolute top-14 right-4 z-50 w-64 bg-zinc-900 border border-line shadow-xl">
          {user && (
            <div className="p-4 border-b border-line">
              <div className="font-medium text-sm">{user.full_name || 'User'}</div>
              <div className="text-xs text-ink-muted">{user.email}</div>
            </div>
          )}
          
          <div className="p-2">
            <button
              onClick={() => {
                setCurrentScreen('role-selection');
                setMenuOpen(false);
              }}
              className="w-full px-4 py-3 text-left text-sm hover:bg-white/10 transition-colors"
            >
              Explore a New Role
            </button>
            <button
              onClick={() => {
                setCurrentScreen('account');
                setMenuOpen(false);
              }}
              className="w-full px-4 py-3 text-left text-sm hover:bg-white/10 transition-colors"
            >
              Account
            </button>
            <button
              onClick={() => {
                handleLogout();
                setMenuOpen(false);
              }}
              className="w-full px-4 py-3 text-left text-sm text-ink-muted hover:bg-white/10 transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================
// SKILLS INPUT SCREEN
// ============================================
// Step between role selection and dashboard. Lets the user mark which skills
// they already have so the dashboard can frame gaps personally. Two paths:
// (1) toggle chips from the role's most-demanded skills, (2) paste text or
// upload a resume; the backend extracts skills and we pre-select them.
const SkillsInputScreen = () => {
  const {
    selectedRole,
    selectedSeniority,
    roleData,
    userSkills,
    setUserSkills,
    setCurrentScreen,
  } = useApp();

  const SENIORITY_LABELS = { All: '', entry: 'entry-level', mid: 'mid-level', senior: 'senior', lead: 'lead/principal' };
  const seniorityLabel = SENIORITY_LABELS[selectedSeniority] ?? '';

  const suggestedSkills = useMemo(() => {
    const all = roleData?.skills || [];
    const sorted = [...all].sort((a, b) => (b.demand || b.job_count || 0) - (a.demand || a.job_count || 0));
    return sorted.slice(0, 30);
  }, [roleData]);

  const [selectedIds, setSelectedIds] = useState(() => new Set((userSkills || []).map(s => s.skill_id)));
  const [resumeText, setResumeText] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState(null);
  const [extractedExtra, setExtractedExtra] = useState([]);
  const [addedExtra, setAddedExtra] = useState([]);
  const [allSkills, setAllSkills] = useState([]);
  const [skillQuery, setSkillQuery] = useState('');
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);
  const fileRef = useRef(null);
  const searchRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api.getAvailableSkills().then(data => {
      if (cancelled) return;
      const flat = [];
      const cats = data?.skills || {};
      Object.values(cats).forEach(arr => (arr || []).forEach(s => flat.push(s)));
      setAllSkills(flat);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const onClick = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSkillDropdown(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  // Redirect if we lost role context (e.g., direct deep-link without state).
  useEffect(() => {
    if (!selectedRole || !roleData) {
      setCurrentScreen('role-selection');
    }
  }, [selectedRole, roleData, setCurrentScreen]);

  const toggle = (skill) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(skill.skill_id)) next.delete(skill.skill_id);
      else next.add(skill.skill_id);
      return next;
    });
  };

  // A new resume / paste replaces the prior extraction outright — the user is
  // reselecting from a fresh source of truth, not appending to the old one.
  const replaceWithExtracted = (extracted) => {
    const list = extracted || [];
    setSelectedIds(new Set(list.map(s => s.skill_id)));
    const suggestedIds = new Set(suggestedSkills.map(s => s.skill_id));
    setExtractedExtra(list.filter(s => !suggestedIds.has(s.skill_id)));
  };

  const handlePaste = async () => {
    if (!resumeText.trim() || resumeText.trim().length < 30) {
      setExtractError('Paste at least a few sentences of resume text.');
      return;
    }
    setExtracting(true);
    setExtractError(null);
    try {
      const data = await api.extractSkillsFromText(resumeText);
      replaceWithExtracted(data.skills || []);
    } catch (err) {
      setExtractError(err.message || 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setExtracting(true);
    setExtractError(null);
    try {
      const data = await api.extractSkillsFromFile(file);
      replaceWithExtracted(data.skills || []);
    } catch (err) {
      setExtractError(err.message || 'Extraction failed');
    } finally {
      setExtracting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const allSelectable = useMemo(() => {
    const map = new Map();
    [...suggestedSkills, ...extractedExtra, ...addedExtra].forEach(s => {
      if (!map.has(s.skill_id)) map.set(s.skill_id, s);
    });
    return [...map.values()];
  }, [suggestedSkills, extractedExtra, addedExtra]);

  // Skills are stored in /api/skills with `id`, but our chip list uses `skill_id`.
  // Normalize when adding from the search dropdown.
  const addSkill = (skill) => {
    const skill_id = skill.skill_id ?? skill.id;
    setAddedExtra(prev => prev.some(s => s.skill_id === skill_id)
      ? prev
      : [...prev, { skill_id, name: skill.name, category: skill.category }]
    );
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.add(skill_id);
      return next;
    });
    setSkillQuery('');
    setShowSkillDropdown(false);
  };

  const skillMatches = useMemo(() => {
    const q = skillQuery.trim().toLowerCase();
    if (!q) return [];
    const existingIds = new Set(allSelectable.map(s => s.skill_id));
    return allSkills
      .filter(s => !existingIds.has(s.id) && s.name.toLowerCase().includes(q))
      .slice(0, 8);
  }, [skillQuery, allSkills, allSelectable]);

  const handleContinue = () => {
    const chosen = allSelectable.filter(s => selectedIds.has(s.skill_id))
      .map(s => ({ skill_id: s.skill_id, name: s.name, category: s.category }));
    setUserSkills(chosen);
    setCurrentScreen('dashboard');
  };

  const handleSkip = () => {
    setUserSkills([]);
    setCurrentScreen('dashboard');
  };

  const selectedCount = selectedIds.size;

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />

      <div className="flex-1">
        <div className="max-w-3xl mx-auto px-8 pt-16 pb-24">
          <div className="mb-10">
            <h1 className="text-5xl md:text-6xl font-semibold mb-6 tracking-tight">
              THE SKILLS YOU HAVE
            </h1>
            <p className="text-xl text-ink-muted">
              Pick the skills you can claim today as a {seniorityLabel} {selectedRole}.
              We'll use this to highlight your gaps — not to judge you.
            </p>
          </div>

        {/* Suggested skill chips */}
        <Panel pad="lg" className="mb-6">
          <label className="block text-sm text-ink-muted mb-4 tracking-wider font-medium">
            SKILLS FOR THIS ROLE
          </label>
          {allSelectable.length === 0 ? (
            <div className="text-ink-muted text-small">No skill data available for this role yet.</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {allSelectable.map(skill => {
                const on = selectedIds.has(skill.skill_id);
                return (
                  <button
                    key={skill.skill_id}
                    onClick={() => toggle(skill)}
                    className={
                      'px-3 py-1.5 text-small border transition-colors ' +
                      (on
                        ? 'bg-white text-black border-white'
                        : 'bg-surface text-ink border-line hover:border-line-strong')
                    }
                  >
                    {skill.name}
                  </button>
                );
              })}
            </div>
          )}
          {/* Add another skill */}
          <div className="mt-5 pt-5 border-t border-line-faint" ref={searchRef}>
            <label className="block text-sm text-ink-muted mb-2 tracking-wider font-medium">
              ADD ANOTHER SKILL
            </label>
            <div className="relative">
              <input
                type="text"
                value={skillQuery}
                onChange={(e) => { setSkillQuery(e.target.value); setShowSkillDropdown(true); }}
                onFocus={() => setShowSkillDropdown(true)}
                placeholder="Search skills…"
                className="w-full bg-black border border-line p-3 text-small text-ink placeholder-ink-faint focus:border-line-strong focus:outline-none"
              />
              {showSkillDropdown && skillQuery && (
                <div className="absolute left-0 right-0 top-full mt-1 bg-zinc-900 border border-line-strong z-10 max-h-60 overflow-y-auto shadow-lg">
                  {skillMatches.length === 0 ? (
                    <div className="px-3 py-2 text-small text-ink-faint">No matching skills.</div>
                  ) : (
                    skillMatches.map(s => (
                      <button
                        key={s.id}
                        onClick={() => addSkill(s)}
                        className="w-full text-left px-3 py-2 text-small text-ink hover:bg-white/10 transition-colors flex items-center justify-between"
                      >
                        <span>{s.name}</span>
                        {s.category && <span className="text-ink-faint text-eyebrow uppercase">{s.category}</span>}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-ink-faint">{selectedCount} selected</span>
            {selectedCount > 0 && (
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-ink-muted hover:text-white transition-colors"
              >
                Unselect all
              </button>
            )}
          </div>
        </Panel>

        {/* Resume input */}
        <Panel pad="lg" className="mb-6">
          <label className="block text-sm text-ink-muted mb-2 tracking-wider font-medium">
            OR EXTRACT FROM YOUR RESUME
          </label>
          <p className="text-small text-ink-muted mb-4">
            Paste your resume text or upload a PDF/DOCX. We'll match what we find against the suggested skills.
          </p>
          <textarea
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            placeholder="Paste resume text here…"
            rows={6}
            className="w-full bg-black border border-line p-3 text-small text-ink placeholder-ink-faint focus:border-line-strong focus:outline-none resize-none"
          />
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <button
              onClick={handlePaste}
              disabled={extracting || !resumeText.trim()}
              className="px-4 py-2 bg-white text-black text-small font-medium hover:bg-ink-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {extracting ? 'Extracting…' : 'Extract from text'}
            </button>
            <span className="text-ink-faint text-small">or</span>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              onChange={handleFile}
              className="hidden"
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={extracting}
              className="px-4 py-2 bg-surface border border-line text-small text-ink hover:border-line-strong disabled:opacity-40 transition-colors"
            >
              Upload PDF or DOCX
            </button>
            {extractError && (
              <span className="text-small text-accent-down">{extractError}</span>
            )}
          </div>
        </Panel>

        {/* Footer actions */}
        <div className="flex items-center justify-between pt-4">
          <div className="flex items-center gap-5">
            <button
              onClick={() => setCurrentScreen('role-selection')}
              className="text-small text-ink-muted hover:text-white transition-colors flex items-center gap-2"
            >
              ← Back
            </button>
            <button
              onClick={handleSkip}
              className="text-small text-ink-muted hover:text-white transition-colors"
            >
              Skip for now
            </button>
          </div>
          <button
            onClick={handleContinue}
            className="px-6 py-3 bg-white text-black text-small font-medium hover:bg-ink-muted transition-colors flex items-center gap-2"
          >
            Continue to dashboard
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
        </div>
      </div>

      <Footer />
    </div>
  );
};

// ============================================
// DASHBOARD SCREEN
// ============================================
const DashboardScreen = () => {
  const {
    selectedRole,
    selectedSeniority,
    setSelectedSeniority,
    selectedLocation,
    setSelectedLocation,
    selectedIndustries,
    setSelectedIndustries,
    selectedCompanies,
    setSelectedCompanies,
    appliedSeniority,
    setAppliedSeniority,
    appliedLocation,
    setAppliedLocation,
    activeTab,
    roleData,
    companies,
    industries,
    seniorities,
    loading,
    setLoading,
    setRoleData,
    setCurrentScreen,
    user,
  } = useApp();

  const [verifyBannerDismissed, setVerifyBannerDismissed] = useState(() => {
    const dismissedAt = parseInt(localStorage.getItem('verifyBannerDismissedAt') || '0', 10);
    return dismissedAt && (Date.now() - dismissedAt) < 24 * 60 * 60 * 1000;
  });
  const [verifyBannerSending, setVerifyBannerSending] = useState(false);
  const [verifyBannerStatus, setVerifyBannerStatus] = useState('');

  const dismissVerifyBanner = () => {
    localStorage.setItem('verifyBannerDismissedAt', String(Date.now()));
    setVerifyBannerDismissed(true);
  };

  const handleBannerResend = async () => {
    setVerifyBannerSending(true);
    setVerifyBannerStatus('');
    try {
      await api.resendVerification();
      setVerifyBannerStatus('Sent — check your inbox.');
    } catch (err) {
      setVerifyBannerStatus(err.message || 'Failed to send.');
    } finally {
      setVerifyBannerSending(false);
    }
  };

  const showVerifyBanner = user && user.email_verified === false && !verifyBannerDismissed;

  // Use APPLIED values for display (what the current data reflects)
  const seniorityLabel = seniorities.find(s => s.id === appliedSeniority)?.label || appliedSeniority;

  // Filter companies by selected industries
  const filteredCompanies = useMemo(() => {
    if (selectedIndustries.includes('All')) return companies;
    return companies.filter(c => c.industry && selectedIndustries.includes(c.industry));
  }, [companies, selectedIndustries]);

  // Reset company selection when industries change
  const prevIndustriesRef = useRef(selectedIndustries);
  useEffect(() => {
    const industriesChanged = JSON.stringify(prevIndustriesRef.current.sort()) !== JSON.stringify([...selectedIndustries].sort());
    if (industriesChanged) {
      setSelectedCompanies(['All']);
      prevIndustriesRef.current = selectedIndustries;
    }
  }, [selectedIndustries, setSelectedCompanies]);

  // Check if any filters differ from "All" defaults
  const hasActiveFilters = 
    !selectedIndustries.includes('All') || 
    !selectedCompanies.includes('All') ||
    !(Array.isArray(selectedLocation) ? selectedLocation.includes('All') : selectedLocation === 'All');

  // Debounced API call - fires when filters change
  const timeoutRef = useRef(null);
  
  const fetchData = useCallback(async (newSeniority, newLocation, newIndustries, newCompanies) => {
    setLoading(true);
    
    const industriesParam = !newIndustries.includes('All') ? newIndustries : null;
    const companiesParam = !newCompanies.includes('All') ? newCompanies.map(id => parseInt(id, 10)) : null;
    
    try {
      const data = await api.getRoleInsights(
        selectedRole,
        newSeniority,
        newLocation,
        industriesParam,
        companiesParam
      );

      if (data.success) {
        setRoleData(data);
      } else {
        setRoleData({
          ...data,
          success: false,
          total_jobs_analyzed: 0,
          skills: [],
          company_count: 0,
          top_companies: [],
          alternative_roles: [],
        });
      }
      
      // Update "applied" state to reflect what data shows
      setAppliedSeniority(newSeniority);
      setAppliedLocation(newLocation);
    } catch (err) {
      console.error('Failed to fetch data:', err);
      setRoleData({
        success: false,
        error: err.message || 'Failed to load data',
        total_jobs_analyzed: 0,
        skills: [],
        company_count: 0,
        top_companies: [],
        alternative_roles: [],
      });
    } finally {
      setLoading(false);
    }
  }, [selectedRole, setLoading, setRoleData, setAppliedSeniority, setAppliedLocation]);

  // Auto-fetch when filters change (debounced)
  const isInitialMount = useRef(true);

  useEffect(() => {
    // Skip the initial mount - we already have data from exploreRole
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    // Clear any pending request
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Debounce by 300ms to batch rapid changes
    timeoutRef.current = setTimeout(async () => {
      setLoading(true);
      
      const industriesParam = !selectedIndustries.includes('All') ? selectedIndustries : null;
      const companiesParam = !selectedCompanies.includes('All') ? selectedCompanies.map(id => parseInt(id, 10)) : null;
      
      try {
        const data = await api.getRoleInsights(
          selectedRole,
          selectedSeniority,
          selectedLocation,
          industriesParam,
          companiesParam
        );

        if (data.success) {
          setRoleData(data);
        } else {
          setRoleData({
            ...data,
            success: false,
            total_jobs_analyzed: 0,
            skills: [],
            company_count: 0,
            top_companies: [],
            alternative_roles: [],
          });
        }
        
        setAppliedSeniority(selectedSeniority);
        setAppliedLocation(selectedLocation);
      } catch (err) {
        console.error('Failed to fetch data:', err);
        setRoleData({
          success: false,
          error: err.message || 'Failed to load data',
          total_jobs_analyzed: 0,
          skills: [],
          company_count: 0,
          top_companies: [],
          alternative_roles: [],
        });
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSeniority, selectedLocation, selectedIndustries, selectedCompanies]);

  // Clear all filters
  const handleClearFilters = () => {
    setSelectedIndustries(['All']);
    setSelectedCompanies(['All']);
    setSelectedLocation(['All']);
  };

  // Guard - redirect if no role data
  useEffect(() => {
    if (!roleData && !loading) {
      setCurrentScreen('role-selection');
    }
  }, [roleData, loading, setCurrentScreen]);

  if (!roleData) {
    return <LoadingScreen />;
  }

  return (
    <div className="min-h-screen bg-black text-white flex flex-col lg:flex-row">
      <DashboardSidebar />
      <MobileHeader />

      {/* Main content - responsive margin */}
      <div className="flex-1 lg:ml-64">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 lg:pt-8 pb-24">

          {showVerifyBanner && (
            <div className="mb-6 px-4 py-3 bg-yellow-500/10 border border-yellow-500/30 flex items-center justify-between gap-4 text-sm">
              <div className="text-yellow-100">
                Verify your email to keep your saved skills and preferences.
                {verifyBannerStatus && (
                  <span className="ml-2 text-ink-muted">{verifyBannerStatus}</span>
                )}
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={handleBannerResend}
                  disabled={verifyBannerSending}
                  className="text-yellow-200 hover:text-white underline underline-offset-2 disabled:opacity-50"
                >
                  {verifyBannerSending ? 'Sending…' : 'Resend link'}
                </button>
                <button
                  onClick={dismissVerifyBanner}
                  aria-label="Dismiss"
                  className="text-ink-muted hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* Header - Responsive */}
          <div className="mb-6 lg:mb-8">
            <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm text-ink-muted mb-2">
              <span>
                {Array.isArray(appliedLocation) 
                  ? appliedLocation.includes('All') 
                    ? 'All Locations' 
                    : appliedLocation.length === 1 
                      ? appliedLocation[0]
                      : `${appliedLocation.length} locations`
                  : appliedLocation
                }
              </span>
              <span>•</span>
              <span>{seniorityLabel}</span>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight mb-3 lg:mb-4">
              {selectedRole}
            </h1>
            <div className="text-base lg:text-lg text-ink-muted">
              Based on <span className="text-white font-medium">
                {roleData?.total_jobs_analyzed?.toLocaleString() || '0'}
              </span> job postings
              {roleData?.company_count > 0 && (
                <span className="text-ink-muted">
                  {' '}from {roleData.company_count} {roleData.company_count === 1 ? 'company' : 'companies'}
                </span>
              )}
            </div>
          </div>

          {/* Filter Bar - Responsive */}
          <div className="mb-6 lg:mb-8 p-3 lg:p-4 bg-surface border border-line">
            <div className="flex flex-wrap items-center gap-2 lg:gap-4">
              <div className="flex items-center gap-2 text-xs lg:text-sm text-ink-muted">
                <Filter className="w-4 h-4" />
                <span className="hidden sm:inline">Filter:</span>
              </div>
              
              {/* Seniority Dropdown */}
              <SingleSelectDropdown
                options={seniorities}
                value={selectedSeniority}
                onChange={setSelectedSeniority}
                getOptionLabel={(s) => s.label}
                getOptionValue={(s) => s.id}
              />

              {/* Location Dropdown */}
              <LocationDropdown
                value={selectedLocation}
                onChange={setSelectedLocation}
              />

              {/* Divider - Hidden on small screens */}
              <div className="hidden sm:block w-px h-6 bg-white/20" />

              {/* Industry Multi-Select */}
              <MultiSelectDropdown
                options={industries}
                selected={selectedIndustries}
                onChange={setSelectedIndustries}
                allLabel="All Industries"
              />

              {/* Company Multi-Select */}
              <MultiSelectDropdown
                options={filteredCompanies}
                selected={selectedCompanies}
                onChange={setSelectedCompanies}
                allLabel="All Companies"
                getOptionLabel={(c) => c.name}
                getOptionValue={(c) => String(c.id)}
              />

              {/* Clear Filters */}
              {hasActiveFilters && (
                <button
                  onClick={handleClearFilters}
                  disabled={loading}
                  className="px-2 lg:px-3 py-2 text-xs lg:text-sm text-ink-muted hover:text-white flex items-center gap-1 transition-colors"
                >
                  <X className="w-3 h-3" />
                  <span className="hidden sm:inline">Clear</span>
                </button>
              )}

              {/* Loading indicator */}
              {loading && (
                <div className="ml-auto flex items-center gap-2 text-xs lg:text-sm text-ink-muted">
                  <DotSpinner size={16} tone="white" />
                  <span className="hidden sm:inline">Updating...</span>
                </div>
              )}
            </div>
          </div>

          {/* Tab Content */}          
          {roleData?.total_jobs_analyzed === 0 ? (
            <NoResultsMessage onClearFilters={handleClearFilters} loading={loading} />
          ) : (
            <>
              {activeTab === 'overview' && <OverviewTab />}
              {activeTab === 'employers' && <EmployersTab />}
              {activeTab === 'skills' && <SkillsTab />}
              {activeTab === 'paths' && <AlternativesTab />}
            </>
          )}
        </div>

        <Footer />
      </div>
    </div>
  );
};

// ============================================
// DASHBOARD SIDEBAR
// ============================================
const DashboardSidebar = () => {
  const { 
    user, 
    activeTab, 
    setActiveTab,
    currentScreen,
    setCurrentScreen, 
    handleLogout 
  } = useApp();

  const tabs = [
    { id: 'overview', label: 'OVERVIEW', description: 'Read the market' },
    { id: 'employers', label: 'COMPANIES', description: 'See who\'s hiring' },
    { id: 'skills', label: 'SKILLS IN DEMAND', description: 'Know what\'s valued' },
    { id: 'paths', label: 'ALTERNATIVE ROLES', description: 'Explore your options' },
  ];

  return (
    <div className="hidden lg:flex w-64 border-r border-line flex-col fixed h-screen bg-zinc-950">
      {/* Logo & User */}
      <div className="p-6 border-b border-line">
        <button 
          onClick={() => setCurrentScreen('landing')}
          className="text-sm font-medium tracking-widest hover:text-ink-muted transition-colors mb-6 block"
        >
          WhatsInDemand
        </button>
        
        {user && (
          <button
            onClick={() => setCurrentScreen('account')}
            className="w-full flex items-center gap-3 p-2 -m-2 rounded hover:bg-surface transition-colors text-left"
          >
            <div className="w-10 h-10 bg-white/10 rounded-full flex items-center justify-center">
              <span className="text-lg font-medium">
                {user.full_name?.charAt(0) || user.email?.charAt(0) || 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm truncate">{user.full_name || 'User'}</div>
              <div className="text-xs text-ink-muted truncate">{user.email}</div>
            </div>
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <div className="space-y-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setCurrentScreen('dashboard');
              }}
              className={`w-full px-4 py-3 text-left transition-colors ${
                activeTab === tab.id && currentScreen === 'dashboard'
                  ? 'bg-white/10 text-white' 
                  : 'text-ink-muted hover:text-white hover:bg-surface'
              }`}
            >
              <div className="text-sm font-medium tracking-wider">{tab.label}</div>
              <div className="text-xs text-ink-muted">{tab.description}</div>
            </button>
          ))}
        </div>
      </nav>

      {/* Bottom Actions */}
      <div className="p-4 border-t border-line space-y-2">
        <button 
          onClick={() => setCurrentScreen('role-selection')}
          className="w-full px-4 py-3 bg-white text-black font-medium text-sm hover:bg-gray-200 transition-colors"
        >
          EXPLORE A NEW ROLE
        </button>
        <button 
          onClick={handleLogout}
          className="w-full px-4 py-3 text-left text-sm text-ink-muted hover:text-white hover:bg-surface transition-colors"
        >
          SIGN OUT
        </button>
      </div>
    </div>
  );
};

// ============================================
// OVERVIEW TAB (STREAMLINED)
// ============================================
// Skills that are intrinsic to almost any role — recommending them as a "gap"
// undermines trust ("Build proficiency in Communication" for an Account Executive).
// Filter these out of the action-strip suggestion.
const INTRINSIC_SKILLS = new Set([
  'communication', 'communications', 'verbal communication', 'written communication',
  'teamwork', 'collaboration', 'leadership', 'problem solving', 'critical thinking',
  'time management', 'organization', 'organizational skills', 'attention to detail',
  'interpersonal skills', 'work ethic', 'adaptability', 'creativity', 'multitasking',
  'professionalism', 'self-motivated', 'self motivated', 'positive attitude',
  'management', 'planning', 'research', 'analysis',
]);

// Skill is intrinsic if (a) it appears in the curated set, or (b) any of its tokens
// appear in the role's normalized title (e.g. "Sales" for an Account Executive,
// "Engineering" for a Software Engineer).
const isIntrinsicSkill = (skillName, roleTitle) => {
  if (!skillName) return false;
  const s = skillName.toLowerCase().trim();
  if (INTRINSIC_SKILLS.has(s)) return true;
  if (!roleTitle) return false;
  const roleTokens = roleTitle.toLowerCase().split(/\s+/).filter(t => t.length > 3);
  return roleTokens.some(tok => s.includes(tok));
};

const OverviewTab = () => {
  const { roleData, selectedRole, setActiveTab, userSkills, setCurrentScreen } = useApp();
  const userSkillIds = useMemo(() => new Set((userSkills || []).map(s => s.skill_id)), [userSkills]);
  const hasUserSkills = userSkillIds.size > 0;

  const skills = roleData?.skills || [];
  const topCompanies = roleData?.top_companies || [];
  const totalJobs = roleData?.total_jobs_analyzed || 0;
  const companyCount = roleData?.company_count || 0;
  const marketTrend = roleData?.market_trend;
  const salaryInfo = roleData?.salary_info;
  const trendData = roleData?.trend_data || [];
  const remoteCount = roleData?.remote_count || 0;
  const onsiteCount = roleData?.onsite_count || 0;
  const remoteTotal = remoteCount + onsiteCount;
  const remoteSharePct = remoteTotal > 0 ? Math.round((remoteCount / remoteTotal) * 100) : null;

  // Verdict: growth direction. Round to integer — decimals on a market-level number look like a bug.
  const rawGrowth = marketTrend?.postings_growth_pct;
  const growthPct = rawGrowth == null ? null : Math.round(rawGrowth);
  const growthDir = growthPct == null ? 'neutral' : growthPct > 0 ? 'up' : growthPct < 0 ? 'down' : 'neutral';
  const verdictLabel = { up: 'Market growing', down: 'Market cooling', neutral: 'Market steady' }[growthDir];
  const verdictNumTone = { up: 'up', down: 'down', neutral: 'default' }[growthDir];
  const verdictNumColor = { up: 'text-accent-up', down: 'text-accent-down', neutral: 'text-ink' }[growthDir];

  // Trend bar chart: honest zero-baseline scale against the largest bar.
  const trendMax = trendData.reduce((m, d) => Math.max(m, d.count || 0), 0) || 1;

  // Action strip: highest-leverage skill that isn't intrinsic to the role.
  // When the user has shared their skills, prefer the highest-demand skill
  // they DON'T have — that's the personalized gap. Otherwise fall back to the
  // role's leverage skill.
  const skillsByDemand = useMemo(
    () => [...skills].sort((a, b) => (b.demand || 0) - (a.demand || 0)),
    [skills]
  );
  const userGapSkill = hasUserSkills
    ? skillsByDemand.find(s => !userSkillIds.has(s.skill_id) && !isIntrinsicSkill(s.name, selectedRole))
    : null;
  const leverageSkill =
    userGapSkill
    || skills.find(s => s.demand >= 40 && s.demand < 95 && !isIntrinsicSkill(s.name, selectedRole))
    || skills.find(s => !isIntrinsicSkill(s.name, selectedRole))
    || skills[0];

  // Coverage stats: how many of the top-demanded skills the user already has.
  const COVERAGE_TOP_N = 15;
  const topMarketSkills = skillsByDemand.slice(0, COVERAGE_TOP_N);
  const coverageHave = topMarketSkills.filter(s => userSkillIds.has(s.skill_id)).length;
  const coveragePct = topMarketSkills.length > 0
    ? Math.round((coverageHave / topMarketSkills.length) * 100)
    : 0;

  // "New"/surging company — only the single most-surging gets the badge.
  // If everything is "new", the badge means nothing.
  const surgingId = (() => {
    const sorted = [...topCompanies]
      .filter(c => typeof c.growth_pct === 'number' && c.growth_pct >= 100)
      .sort((a, b) => b.growth_pct - a.growth_pct);
    return sorted[0]?.id ?? null;
  })();

  // Top-3 highlight companies for the verdict prose
  const highlightCos = [...topCompanies]
    .sort((a, b) => (b.growth_pct ?? -Infinity) - (a.growth_pct ?? -Infinity))
    .slice(0, 3)
    .filter(c => (c.growth_pct ?? 0) > 0);

  // Format salary with currency support
  const formatSalary = (value, currency = 'USD') => {
    if (!value) return '—';
    
    const symbols = {
      'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹',
      'CAD': 'C$', 'AUD': 'A$', 'SGD': 'S$', 'JPY': '¥',
    };
    const symbol = symbols[currency] || '$';
    
    // Handle INR lakhs
    if (currency === 'INR' && value >= 100000) {
      return `${symbol}${(value / 100000).toFixed(1)}L`;
    }
    
    if (value >= 1000) {
      return `${symbol}${Math.round(value / 1000)}K`;
    }
    return `${symbol}${value.toLocaleString()}`;
  };

  const formatMonth = (dateStr) => new Date(dateStr).toLocaleDateString('en-US', { month: 'short' });

  return (
    <div className="space-y-4">

      {/* ACTION STRIP — one specific thing to do */}
      {leverageSkill && (
        <div className="flex items-start gap-3 p-4 bg-accent-warn/10 border border-accent-warn/20">
          <Clock className="w-5 h-5 text-accent-warn flex-shrink-0 mt-0.5" />
          <div>
            <Eyebrow className="text-accent-warn mb-1">
              {hasUserSkills ? 'Your top gap' : 'One thing to do this month'}
            </Eyebrow>
            <div className="text-body text-ink">
              {hasUserSkills ? (
                <>
                  You have <span className="num">{coverageHave}</span> of the top <span className="num">{topMarketSkills.length}</span> skills for this market.
                  Closest leverage win: <strong className="text-accent-warn font-medium">{leverageSkill.name}</strong>
                  {leverageSkill.demand != null && <> (<span className="num">{leverageSkill.demand}%</span> of postings)</>}.
                </>
              ) : (
                <>
                  Build proficiency in <strong className="text-accent-warn font-medium">{leverageSkill.name}</strong>
                  {leverageSkill.job_count ? <> — it shows up in <span className="num">{leverageSkill.job_count.toLocaleString()}</span> postings </> : ' — it appears in '}
                  (<span className="num">{leverageSkill.demand}%</span> of this market) and is your highest-leverage skill right now.
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* VERDICT CARD — growth % is the single hero number */}
      <Panel>
        <div className="flex items-center gap-2 mb-3">
          <Pill tone={growthDir}>{verdictLabel}</Pill>
          <span className="text-small text-ink-faint">Updated today</span>
        </div>

        <div className="flex items-baseline gap-3 mb-2">
          {growthPct != null ? (
            <HeroNumber tone={verdictNumTone} value={`${growthPct > 0 ? '+' : ''}${growthPct}%`} />
          ) : (
            <HeroNumber tone="default" value="—" className="text-ink-faint" />
          )}
          <Eyebrow className="text-ink-faint">vs previous month</Eyebrow>
        </div>

        {highlightCos.length > 0 && (
          <div className="text-body text-ink">
            Growth driven by{' '}
            {highlightCos.map((c, i) => (
              <React.Fragment key={c.id}>
                <span className={verdictNumColor}>{c.name}</span>
                {i < highlightCos.length - 1 ? (i === highlightCos.length - 2 ? ', and ' : ', ') : ''}
              </React.Fragment>
            ))}
            .
          </div>
        )}

        <p className="text-meta text-ink-faint mt-2">
          Recently added companies are excluded for accurate comparisons.
        </p>
      </Panel>

      {/* TWO-COL: Companies hiring now | Posting trend sparkline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">

        {/* WHO'S HIRING */}
        <Panel>
          <Eyebrow className="mb-3">Who's hiring right now</Eyebrow>
          {topCompanies.length > 0 ? (
            <>
              <div>
                {topCompanies.slice(0, 5).map((company, idx) => (
                  <div key={company.id} className="flex items-center py-2 border-b border-line-faint last:border-b-0">
                    <span className="num text-small text-ink-faint w-4 flex-shrink-0">{idx + 1}</span>
                    <span className="text-body text-ink flex-1 px-2 truncate">{company.name}</span>
                    {company.id === surgingId && (
                      <span className="text-[9px] px-1.5 py-0.5 bg-accent-up/15 text-accent-up font-medium mr-2 flex-shrink-0 uppercase tracking-wider">
                        new
                      </span>
                    )}
                    <span className="num text-meta text-ink-muted whitespace-nowrap">
                      {company.job_count?.toLocaleString()}
                      {typeof company.growth_pct === 'number' && company.growth_pct > 0 && (
                        <span className="text-accent-up ml-1">↑</span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setActiveTab('employers')}
                className="mt-3 text-meta text-ink-muted hover:text-ink transition-colors inline-flex items-center gap-1"
              >
                View all <span className="num">{companyCount}</span> <ArrowRight className="w-3 h-3" />
              </button>
            </>
          ) : (
            <div className="text-body text-ink-faint">No company data</div>
          )}
        </Panel>

        {/* POSTING TREND — bar chart with readable labels */}
        <Panel>
          <Eyebrow className="mb-4">Active openings — same companies, 4-month view</Eyebrow>
          {trendData.length > 0 ? (
            <>
              <div className="flex items-end gap-2 h-32 mb-2">
                {trendData.map((d, i) => {
                  const isLast = i === trendData.length - 1;
                  const isPartial = !!d.is_partial;
                  const c = d.count || 0;
                  const h = Math.min(100, Math.max(2, (c / trendMax) * 100));
                  const numTone = isPartial ? 'text-ink' : (isLast ? 'text-accent-up' : 'text-ink-muted');
                  const barClass = `w-full ${isPartial ? 'bg-ink/90 border-t border-dashed border-ink' : (isLast ? 'bg-accent-up' : 'bg-ink-ghost')}`;
                  return (
                    <div
                      key={d.date}
                      className="flex-1 flex flex-col items-center justify-end h-full"
                      title={`${formatMonth(d.date)}${isPartial ? ' (MTD)' : ''}: ${d.count.toLocaleString()} jobs`}
                    >
                      <div className={`num text-small font-medium mb-1 ${numTone}`}>
                        {d.count.toLocaleString()}{isPartial ? ' (MTD)' : ''}
                      </div>
                      <div
                        className={barClass}
                        style={{ height: `${h}%` }}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-2">
                {trendData.map((d, i) => {
                  const isLast = i === trendData.length - 1;
                  const isPartial = !!d.is_partial;
                  const labelTone = isPartial ? 'text-ink-muted' : (isLast ? 'text-accent-up font-medium' : 'text-ink-muted');
                  return (
                    <div key={d.date} className="flex-1 text-center">
                      <span className={`text-small ${labelTone}`}>
                        {formatMonth(d.date)}
                      </span>
                    </div>
                  );
                })}
              </div>
              <p className="text-meta text-ink-faint mt-2">
                Recently added companies are excluded until they have 4+ months of history, so each month compares the same set of companies.
              </p>
            </>
          ) : (
            <div className="h-32 flex items-center justify-center text-body text-ink-faint text-center px-4">
              Not enough history yet — we'll show this once 4 months of stable scrape data exist for this role.
            </div>
          )}
        </Panel>
      </div>

      {/* METRICS ROW — things the user actually wants to know */}
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Active postings" value={totalJobs.toLocaleString()} />
        <Stat label="Companies hiring" value={companyCount.toLocaleString()} />
        <Stat
          label="Remote share"
          value={remoteSharePct == null ? '—' : `${remoteSharePct}%`}
          hint={remoteSharePct == null ? 'No location data' : `${remoteCount.toLocaleString()} of ${remoteTotal.toLocaleString()} jobs`}
        />
      </div>

      {/* SALARY */}
      <Panel>
        <Eyebrow className="mb-3">Salary</Eyebrow>
        {salaryInfo && salaryInfo.median ? (
          (() => {
            const min = salaryInfo.min || 0;
            const max = salaryInfo.max || min;
            const med = salaryInfo.median;
            const pct = max > min ? Math.round(((med - min) / (max - min)) * 100) : 50;
            return (
              <>
                <div className="flex items-baseline gap-1.5 mb-2">
                  <HeroNumber value={formatSalary(med)} />
                  <Eyebrow className="text-ink-faint">median</Eyebrow>
                </div>
                <div className="relative h-[3px] bg-line mb-1.5">
                  <div className="absolute top-0 left-0 h-[3px] bg-accent-up" style={{ width: `${pct}%` }} />
                  <div
                    className="absolute w-2.5 h-2.5 bg-accent-up"
                    style={{ top: '-3.5px', left: `${pct}%`, transform: 'translateX(-50%)' }}
                  />
                </div>
                <div className="text-small text-ink-faint">
                  Range: <span className="num">{formatSalary(min)}</span> — <span className="num">{formatSalary(max)}</span>
                  {salaryInfo.jobs_with_salary ? (
                    <span className="text-ink-ghost"> · <span className="num">{salaryInfo.jobs_with_salary.toLocaleString()}</span> jobs (<span className="num">{salaryInfo.salary_coverage_pct}%</span>)</span>
                  ) : null}
                </div>
              </>
            );
          })()
        ) : (
          <div className="text-body text-ink-faint">Not enough salary data for this filter</div>
        )}
      </Panel>

      <button
        onClick={() => setCurrentScreen('skills-input')}
        className="w-full p-5 border border-dashed border-line-strong text-left hover:bg-surface transition-colors group"
      >
        <Eyebrow className="text-ink-muted mb-2">Your skill coverage</Eyebrow>
        <div className="text-body text-ink mb-1">
          You have <span className="num">{coverageHave}</span> of the top <span className="num">{topMarketSkills.length}</span> most-demanded skills (<span className="num">{coveragePct}%</span>).
        </div>
        <div className="text-meta text-ink-muted inline-flex items-center gap-1 group-hover:text-ink transition-colors">
          Update skills <ArrowRight className="w-3 h-3" />
        </div>
      </button>
    </div>
  );
};


// ============================================
// EMPLOYERS TAB
// ============================================
const EmployersTab = () => {
  const { roleData } = useApp();
  const [sortColumn, setSortColumn] = useState('jobs');
  const [sortDirection, setSortDirection] = useState('desc');

  const topCompanies = roleData?.top_companies || [];

  // Sort companies
  const sortedCompanies = [...topCompanies].sort((a, b) => {
    let aVal, bVal;

    switch (sortColumn) {
      case 'name':
        aVal = a.name?.toLowerCase() || '';
        bVal = b.name?.toLowerCase() || '';
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      case 'industry':
        aVal = a.industry?.toLowerCase() || '';
        bVal = b.industry?.toLowerCase() || '';
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      case 'growth':
        // Treat null/undefined as -Infinity for sorting
        aVal = a.growth_pct ?? -Infinity;
        bVal = b.growth_pct ?? -Infinity;
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      case 'jobs':
      default:
        aVal = a.job_count || 0;
        bVal = b.job_count || 0;
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
    }
  });

  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  const SortHeader = ({ column, label, className = '' }) => (
    <button
      onClick={() => handleSort(column)}
      className={`flex items-center gap-1 hover:text-white transition-colors ${className}`}
    >
      {label}
      <span className="text-xs">
        {sortColumn === column ? (
          sortDirection === 'asc' ? '↑' : '↓'
        ) : (
          <span className="text-ink-faint">↕</span>
        )}
      </span>
    </button>
  );

  // Calculate totals
  const totalJobs = sortedCompanies.reduce((sum, c) => sum + (c.job_count || 0), 0);

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="text-sm text-ink-muted">
          Showing <span className="text-white font-medium">{sortedCompanies.length}</span> employers
          {totalJobs > 0 && (
            <span className="text-ink-muted"> • {totalJobs.toLocaleString()} total jobs</span>
          )}
        </div>
      </div>

      {/* Employers Table */}
      <div className="bg-surface border border-line overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-line text-xs font-medium text-ink-muted tracking-wider">
          <div className="col-span-4">
            <SortHeader column="name" label="COMPANY" />
          </div>
          <div className="col-span-3">
            <SortHeader column="industry" label="INDUSTRY" />
          </div>
          <div className="col-span-3 text-right">
            <SortHeader column="jobs" label="CURRENT OPENINGS" className="justify-end" />
          </div>
          <div className="col-span-2 text-right">
            <SortHeader column="growth" label="GROWTH (Δ)" className="justify-end" />
          </div>
        </div>

        {/* Rows */}
        <div className="divide-y divide-white/5">
          {sortedCompanies.length === 0 ? (
            <div className="px-6 py-12 text-center text-ink-muted">
              No employers found matching your criteria.
            </div>
          ) : (
            sortedCompanies.map((company, idx) => (
              <div
                key={company.id}
                className="grid grid-cols-12 gap-4 px-6 py-4 hover:bg-surface transition-colors"
              >
                {/* Company Name */}
                <div className="col-span-4">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-ink-faint w-6">{idx + 1}</span>
                    <span className="font-medium">{company.name}</span>
                  </div>
                </div>

                {/* Industry */}
                <div className="col-span-3">
                  {company.industry ? (
                    <span className="px-2 py-1 text-xs bg-white/10 border border-line text-ink">
                      {company.industry}
                    </span>
                  ) : (
                    <span className="text-ink-faint">—</span>
                  )}
                </div>

                {/* Job Count */}
                <div className="col-span-3">
                  <span className="font-medium">{company.job_count?.toLocaleString() || '—'}</span>
                </div>

                {/* Growth */}
                <div className="col-span-2">
                  {company.growth_pct != null ? (
                    <span className={`font-medium ${
                      company.growth_pct > 0 ? 'text-accent-up' :
                      company.growth_pct < 0 ? 'text-accent-down' :
                      'text-ink-muted'
                    }`}>
                      {company.growth_pct > 0 ? '+' : ''}
                      {company.growth_pct}%
                    </span>
                  ) : (
                    <span className="text-ink-faint">—</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer Note */}
      {sortedCompanies.some(c => c.growth_pct == null) && (
        <div className="text-xs text-ink-muted text-center">
          Growth rate vs 90 days ago. — indicates insufficient data.
        </div>
      )}
    </div>
  );
};

// ============================================
// SKILLS TAB (Explore Skills)
// ============================================
const SkillsTab = () => {
  const { roleData, userSkills } = useApp();
  const [sortColumn, setSortColumn] = useState('demand');
  const [sortDirection, setSortDirection] = useState('desc');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [selectedSkill, setSelectedSkill] = useState(null);

  const skills = roleData?.skills || [];
  const userSkillIds = useMemo(() => new Set((userSkills || []).map(s => s.skill_id)), [userSkills]);
  const hasUserSkills = userSkillIds.size > 0;

  const filteredSkills = categoryFilter === 'All'
    ? skills
    : skills.filter(s => s.category === categoryFilter);

  // Sort skills
  const sortedSkills = [...filteredSkills].sort((a, b) => {
    let aVal, bVal;
    
    switch (sortColumn) {
      case 'name':
        aVal = a.name?.toLowerCase() || '';
        bVal = b.name?.toLowerCase() || '';
        return sortDirection === 'asc' 
          ? aVal.localeCompare(bVal) 
          : bVal.localeCompare(aVal);
      case 'category':
        aVal = a.category?.toLowerCase() || '';
        bVal = b.category?.toLowerCase() || '';
        return sortDirection === 'asc' 
          ? aVal.localeCompare(bVal) 
          : bVal.localeCompare(aVal);
      case 'growth':
        // Treat null as -Infinity so they sort to the bottom
        aVal = a.growth_pct ?? -Infinity;
        bVal = b.growth_pct ?? -Infinity;
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      case 'jobs':
        aVal = a.job_count || 0;
        bVal = b.job_count || 0;
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      case 'have':
        aVal = userSkillIds.has(a.skill_id) ? 1 : 0;
        bVal = userSkillIds.has(b.skill_id) ? 1 : 0;
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      case 'demand':
      default:
        aVal = a.demand || 0;
        bVal = b.demand || 0;
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
    }
  });

  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  const SortHeader = ({ column, label, className = '' }) => (
    <button 
      onClick={() => handleSort(column)}
      className={`flex items-center gap-1 hover:text-white transition-colors ${className}`}
    >
      {label}
      <span className="text-xs">
        {sortColumn === column ? (
          sortDirection === 'asc' ? '↑' : '↓'
        ) : (
          <span className="text-ink-faint">↕</span>
        )}
      </span>
    </button>
  );

  const categories = [...new Set(skills.map(s => s.category).filter(Boolean))];

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="text-sm text-ink-muted">
          Showing <span className="text-white font-medium">{sortedSkills.length}</span> skills
        </div>
        <div className="flex-1" />
        <SingleSelectDropdown
          options={[
            { value: 'All', label: 'All Categories' },
            ...categories.map(cat => ({ value: cat, label: cat.charAt(0).toUpperCase() + cat.slice(1) }))
          ]}
          value={categoryFilter}
          onChange={setCategoryFilter}
          getOptionLabel={(opt) => opt.label}
          getOptionValue={(opt) => opt.value}
        />
      </div>

      {/* Skills Table */}
      <div className="bg-surface border border-line overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-line text-xs font-medium text-ink-muted tracking-wider">
          <div className="col-span-3">
            <SortHeader column="name" label="SKILL" />
          </div>

          <div className="col-span-2">
            <SortHeader column="category" label="CATEGORY" />
          </div>

          <div className="col-span-4 pr-6">
            <SortHeader column="demand" label="CURRENT DEMAND" />
          </div>

          <div className="col-span-2 pl-6 border-l border-line">
            <SortHeader column="growth" label="GROWTH (Δ)" />
          </div>

          <div className="col-span-1 pl-4 border-l border-line">
            <SortHeader column="have" label="YOU" className="justify-center w-full" />
          </div>
        </div>

        {/* Rows */}
        <div className="divide-y divide-white/5">
          {sortedSkills.length === 0 ? (
            <div className="px-6 py-12 text-center text-ink-muted">
              No skills found matching your criteria.
            </div>
          ) : (
            sortedSkills.map((skill, idx) => {
              const userHas = hasUserSkills && userSkillIds.has(skill.skill_id);
              return (
              <button
                key={skill.skill_id || idx}
                onClick={() => setSelectedSkill(skill)}
                className="w-full grid grid-cols-12 gap-4 px-6 py-4 hover:bg-surface transition-colors text-left items-center"
              >
                <div className="col-span-3">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-ink-faint w-6">{idx + 1}</span>
                    <span className="font-medium">{skill.name}</span>
                  </div>
                </div>

                <div className="col-span-2">
                  <span className="px-2 py-1 text-xs font-medium bg-white/10 text-gray-200 border border-line">
                    {(skill.category || 'other').toUpperCase()}
                  </span>
                </div>

                <div className="col-span-4 pr-6">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                      <div className="h-full bg-white" style={{ width: `${skill.demand}%` }} />
                    </div>
                    <span className="text-sm font-medium w-14 text-right">{skill.demand}%</span>
                  </div>
                  <div className="mt-1 text-xs text-ink-muted">
                    {skill.job_count?.toLocaleString() || '—'} jobs
                  </div>
                </div>
                <div className="col-span-2 pl-6 border-l border-line">
                  {skill.growth_pct != null ? (
                    <span className={`text-sm font-medium ${
                      skill.growth_pct > 0 ? 'text-accent-up' :
                      skill.growth_pct < 0 ? 'text-accent-down' :
                      'text-ink-muted'
                    }`}>
                      {skill.growth_pct > 0 ? '+' : ''}
                      {skill.growth_pct}%
                    </span>
                  ) : (
                    <span className="text-sm text-ink-faint">—</span>
                  )}
                </div>
                <div className="col-span-1 pl-4 border-l border-line text-center">
                  {!hasUserSkills ? (
                    <span className="text-ink-faint text-sm">—</span>
                  ) : userHas ? (
                    <span className="text-accent-up text-base font-medium" title="You have this skill">✓</span>
                  ) : (
                    <span className="text-ink-faint text-base" title="Gap">·</span>
                  )}
                </div>
              </button>
              );
            })
          )}
        </div>
      </div>

      {/* Skill Detail Modal */}
      {selectedSkill && (
        <SkillDetailModal 
          skill={selectedSkill} 
          onClose={() => setSelectedSkill(null)} 
        />
      )}
    </div>
  );
};

// ============================================
// SKILL DETAIL MODAL
// ============================================
const SkillDetailModal = ({ skill, onClose }) => {
  const { selectedRole } = useApp();

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // Close on backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-zinc-900 border border-line-strong max-w-lg w-full max-h-[80vh] overflow-y-auto">
        <div className="p-6 border-b border-line flex items-center justify-between">
          <h2 className="text-2xl font-semibold">{skill.name}</h2>
          <button 
            onClick={onClose} 
            className="text-ink-muted hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <div className="p-6 space-y-6">
          {/* Demand */}
          <div>
            <div className="text-sm text-ink-muted mb-2">DEMAND FOR {selectedRole?.toUpperCase()}</div>
            <div className="flex items-center gap-4">
              <div className="text-5xl font-semibold">{skill.demand}%</div>
              <div className="text-ink-muted">
                of jobs require this skill
              </div>
            </div>
          </div>

          {/* Category */}
          <div>
            <div className="text-sm text-ink-muted mb-2">CATEGORY</div>
            <span className="px-3 py-1 text-sm font-medium bg-white/10 text-gray-200 border border-line">
              {(skill.category || 'other').toUpperCase()}
            </span>
          </div>

          {/* Job Count */}
          <div>
            <div className="text-sm text-ink-muted mb-2">APPEARING IN</div>
            <div className="text-2xl font-medium">
              {skill.job_count?.toLocaleString() || '—'} jobs
            </div>
          </div>

          {/* Learning Resources */}
          <div className="pt-4 border-t border-line">
            <div className="text-sm text-ink-muted mb-3">LEARN THIS SKILL</div>
            <div className="space-y-2">
              <a 
                href={`https://www.coursera.org/search?query=${encodeURIComponent(skill.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full p-3 bg-surface border border-line hover:bg-white/10 transition-colors text-left flex items-center justify-between"
              >
                <span>Search on Coursera</span>
                <ExternalLink className="w-4 h-4 text-ink-muted" />
              </a>
              <a 
                href={`https://www.udemy.com/courses/search/?q=${encodeURIComponent(skill.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full p-3 bg-surface border border-line hover:bg-white/10 transition-colors text-left flex items-center justify-between"
              >
                <span>Search on Udemy</span>
                <ExternalLink className="w-4 h-4 text-ink-muted" />
              </a>
              <a 
                href={`https://www.youtube.com/results?search_query=${encodeURIComponent(skill.name + ' tutorial')}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full p-3 bg-surface border border-line hover:bg-white/10 transition-colors text-left flex items-center justify-between"
              >
                <span>Search on YouTube</span>
                <ExternalLink className="w-4 h-4 text-ink-muted" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// PATHS TAB (WITH SALARY RANGE)
// ============================================
// ============================================
// PATHS TAB (FIXED)
// ============================================
const AlternativesTab = () => {
  const { 
    roleData, 
    selectedRole, 
    switchToRole,
    loading
  } = useApp();

  const alternativeRoles = roleData?.alternative_roles || [];

  // Format salary with currency support
  const formatSalary = (value) => {
    if (!value) return '—';
    if (value >= 1000) {
      return `$${Math.round(value / 1000)}K`;
    }
    return `$${value.toLocaleString()}`;
  };

  const formatSalaryRange = (min, max, currency = 'USD') => {
    if (!min && !max) return null;
    if (min && max && min !== max) {
      return `${formatSalary(min, currency)} - ${formatSalary(max, currency)}`;
    }
    if (min) return formatSalary(min, currency);
    return null;
  };

  const handleExploreRole = async (roleTitle) => {
    await switchToRole(roleTitle);
  };

  return (
    <div className="space-y-6">
      <div className="text-ink-muted">
        Based on skill overlap with <span className="text-white font-medium">{selectedRole}</span>, 
        here are roles you might also consider.
      </div>

      {alternativeRoles.length === 0 ? (
        <div className="p-12 bg-surface border border-line text-center">
          <div className="text-xl font-medium mb-2">No close matches yet</div>
          <div className="text-ink-muted max-w-md mx-auto">
            We couldn't find adjacent roles with enough postings and shared skills to recommend confidently. Try a broader location or seniority filter.
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {alternativeRoles.map((role, idx) => (
            <div 
              key={idx}
              className="p-6 bg-surface border border-line hover:bg-white/[0.07] transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold mb-1">{role.title}</h3>
                  <div className="text-sm text-ink-muted flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>{role.job_count?.toLocaleString() || '—'} open positions</span>
                    {role.posting_growth_pct != null && (
                      <span className={`font-medium ${
                        role.posting_growth_pct > 0 ? 'text-accent-up' :
                        role.posting_growth_pct < 0 ? 'text-accent-down' :
                        'text-ink-muted'
                      }`}>
                        ({role.posting_growth_pct > 0 ? '+' : ''}{role.posting_growth_pct}% growth)
                      </span>
                    )}
                  </div>
                  
                  {(role.salary_min || role.salary_max) && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-accent-up font-medium">
                        {formatSalaryRange(role.salary_min, role.salary_max)}
                      </span>
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <div className={`text-3xl font-semibold ${
                    role.skill_overlap >= 70 ? 'text-accent-up' :
                    role.skill_overlap >= 50 ? 'text-yellow-500' :
                    'text-orange-500'
                  }`}>
                    {role.skill_overlap}%
                  </div>
                  <div className="text-xs text-ink-muted">SKILL OVERLAP</div>
                </div>
              </div>

              {/* Shared Skills */}
              {role.shared_skills && role.shared_skills.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs text-ink-muted mb-2">SHARED SKILLS</div>
                  <div className="flex flex-wrap gap-2">
                    {role.shared_skills.slice(0, 6).map((skill, skillIdx) => (
                      <span 
                        key={skillIdx}
                        className="px-2 py-1 bg-accent-up/20 border border-green-500/30 text-xs text-accent-up"
                      >
                        {skill}
                      </span>
                    ))}
                    {role.shared_skills.length > 6 && (
                      <span className="px-2 py-1 text-xs text-ink-muted">
                        +{role.shared_skills.length - 6} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Skills You'd Need to Learn */}
              {role.new_skills && role.new_skills.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs text-ink-muted mb-2">SKILLS GAP</div>
                  <div className="flex flex-wrap gap-2">
                    {role.new_skills.slice(0, 4).map((skill, skillIdx) => (
                      <span 
                        key={skillIdx}
                        className="px-2 py-1 bg-orange-500/20 border border-orange-500/30 text-xs text-orange-400"
                      >
                        {skill}
                      </span>
                    ))}
                    {role.new_skills.length > 4 && (
                      <span className="px-2 py-1 text-xs text-ink-muted">
                        +{role.new_skills.length - 4} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Action Button */}
              <button
                onClick={() => handleExploreRole(role.title)}
                disabled={loading}
                className={`px-4 py-2 font-medium text-sm flex items-center gap-2 transition-colors ${
                  loading 
                    ? 'bg-white/20 text-ink-muted cursor-not-allowed' 
                    : 'bg-white text-black hover:bg-gray-200'
                }`}
              >
                {loading ? (
                  <>
                    <DotSpinner size={16} tone="black" />
                    LOADING...
                  </>
                ) : (
                  <>
                    EXPLORE THIS ROLE
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================
// LOADING SCREEN
// ============================================
// Dots-in-circle spinner. `size` is the wrapper diameter in px; dots are sized
// proportionally. `tone` selects dot color (white on dark, black on light).
const DotSpinner = ({ size = 48, tone = 'white', className = '' }) => {
  const dot = Math.max(2, Math.round(size / 8));
  const radius = Math.round(size / 2 - dot / 2 - 1);
  const dotBg = tone === 'black' ? 'bg-black' : 'bg-white';
  return (
    <div
      className={`relative animate-spin ${className}`}
      style={{ width: size, height: size, animationDuration: '1.2s' }}
    >
      {Array.from({ length: 8 }).map((_, i) => (
        <span
          key={i}
          className={`absolute block ${dotBg}`}
          style={{
            width: dot,
            height: dot,
            top: '50%',
            left: '50%',
            marginTop: -dot / 2,
            marginLeft: -dot / 2,
            transform: `rotate(${i * 45}deg) translate(0, -${radius}px)`,
            opacity: 0.3 + 0.7 * ((i + 1) / 8),
          }}
        />
      ))}
    </div>
  );
};

const LoadingScreen = () => (
  <div className="min-h-screen bg-black text-white flex items-center justify-center">
    <div className="text-center">
      <div className="mb-8 flex justify-center">
        <DotSpinner size={48} tone="white" />
      </div>
      <div className="text-3xl font-semibold mb-4">ANALYZING</div>
      <div className="text-ink-muted">Gathering market intelligence...</div>
    </div>
  </div>
);

// ============================================
// INITIAL LOADING SCREEN (for app startup)
// ============================================
const InitialLoadingScreen = () => (
  <div className="min-h-screen bg-black text-white flex items-center justify-center">
    <div className="text-center">
      <div className="mb-8 flex justify-center">
        <DotSpinner size={48} tone="white" />
      </div>
      <div className="text-lg font-medium tracking-widest">WhatsInDemand</div>
    </div>
  </div>
);

// ============================================
// FORGOT PASSWORD
// ============================================
const ForgotPasswordScreen = () => {
  const { setCurrentScreen } = useApp();
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      setError(err.message || 'Could not send reset email.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />
      <div className="flex-1">
        <div className="max-w-md mx-auto px-6 pt-16 pb-24">
          <h1 className="text-4xl font-semibold mb-3 tracking-tight">FORGOT PASSWORD</h1>
          <p className="text-ink-muted text-sm mb-6">
            Enter your email and we'll send you a link to reset it.
          </p>

          <ErrorMessage error={error} onClose={() => setError(null)} />

          {submitted ? (
            <div className="p-4 bg-surface border border-line-strong text-sm">
              A reset link has been sent to <span className="font-medium">{email}</span>. Please check your inbox (and spam folder).
            </div>
          ) : (
            <form onSubmit={onSubmit}>
              <input
                type="email"
                placeholder="Email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors mb-4"
                autoComplete="email"
                required
              />
              <button
                type="submit"
                disabled={submitting || !email}
                className={`w-full py-3 font-medium text-sm tracking-wide transition-colors ${
                  !submitting && email
                    ? 'bg-white text-black hover:bg-gray-200'
                    : 'bg-white/10 text-ink-faint cursor-not-allowed'
                }`}
              >
                {submitting ? 'SENDING...' : 'SEND RESET LINK'}
              </button>
            </form>
          )}

          <div className="text-center text-ink-muted text-sm mt-6">
            Remembered it?{' '}
            <button onClick={() => setCurrentScreen('login')} className="text-white underline hover:text-ink">
              Back to sign in
            </button>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

// ============================================
// RESET PASSWORD
// ============================================
const ResetPasswordScreen = () => {
  const { setCurrentScreen, setUser } = useApp();
  const location = useLocation();
  const token = useMemo(() => new URLSearchParams(location.search).get('token'), [location.search]);

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!token) return setError('Reset link is missing a token.');
    if (password.length < 8) return setError('Password must be at least 8 characters.');
    if (password !== confirm) return setError('Passwords do not match.');

    setSubmitting(true);
    try {
      const data = await api.resetPassword(token, password);
      if (data.user) setUser(data.user);
      setCurrentScreen('dashboard');
    } catch (err) {
      setError(err.message || 'Reset failed. The link may be expired or already used.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />
      <div className="flex-1">
        <div className="max-w-md mx-auto px-6 pt-16 pb-24">
          <h1 className="text-4xl font-semibold mb-3 tracking-tight">RESET PASSWORD</h1>
          <p className="text-ink-muted text-sm mb-6">Choose a new password for your account.</p>

          <ErrorMessage error={error} onClose={() => setError(null)} />

          <form onSubmit={onSubmit}>
            <div className="space-y-3 mb-6">
              <input
                type="password"
                placeholder="New password (min 8 chars)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="new-password"
                required
              />
              <input
                type="password"
                placeholder="Confirm new password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full px-4 py-3 bg-surface border border-line-strong text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="new-password"
                required
              />
            </div>
            <button
              type="submit"
              disabled={submitting || !password || !confirm}
              className={`w-full py-3 font-medium text-sm tracking-wide transition-colors ${
                !submitting && password && confirm
                  ? 'bg-white text-black hover:bg-gray-200'
                  : 'bg-white/10 text-ink-faint cursor-not-allowed'
              }`}
            >
              {submitting ? 'UPDATING...' : 'UPDATE PASSWORD'}
            </button>
          </form>

          <div className="text-center text-ink-muted text-sm mt-6">
            <button onClick={() => setCurrentScreen('forgot-password')} className="text-white underline hover:text-ink">
              Need a new link?
            </button>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

// ============================================
// VERIFY EMAIL
// ============================================
const VerifyEmailScreen = () => {
  const { setUser, setCurrentScreen, user, initialLoading } = useApp();
  const location = useLocation();
  const token = useMemo(() => new URLSearchParams(location.search).get('token'), [location.search]);
  const [state, setState] = useState('verifying'); // 'verifying' | 'success' | 'error'
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (initialLoading) return;
    let cancelled = false;
    (async () => {
      if (!token) {
        setState('error');
        setMessage('Verification link is missing a token.');
        return;
      }
      try {
        const data = await api.verifyEmail(token);
        if (cancelled) return;
        if (data.user) setUser(data.user);
        setState('success');
        setMessage(data.message || 'Email verified.');
      } catch (err) {
        if (cancelled) return;
        setState('error');
        setMessage(err.message || 'This link is invalid or expired.');
      }
    })();
    return () => { cancelled = true; };
  }, [token, setUser, initialLoading]);

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />
      <div className="flex-1">
        <div className="max-w-md mx-auto px-6 pt-16 pb-24 text-center">
          <h1 className="text-4xl font-semibold mb-6 tracking-tight">EMAIL VERIFICATION</h1>
          {state === 'verifying' && (
            <div className="text-ink-muted">Verifying your email…</div>
          )}
          {state === 'success' && (
            <>
              <div className="p-4 bg-surface border border-line-strong text-sm mb-6">{message}</div>
              <button
                onClick={() => setCurrentScreen(user ? 'dashboard' : 'login')}
                className="px-6 py-3 bg-white text-black font-medium text-sm hover:bg-gray-200 transition-colors"
              >
                CONTINUE
              </button>
            </>
          )}
          {state === 'error' && (
            <>
              <div className="p-4 bg-accent-down/20 border border-red-500 text-accent-down text-sm mb-6">{message}</div>
              <button
                onClick={() => setCurrentScreen(user ? 'account' : 'login')}
                className="px-6 py-3 border border-line-strong text-sm hover:bg-white/5 transition-colors"
              >
                BACK
              </button>
            </>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
};

// ============================================
// 404
// ============================================
const NotFoundScreen = () => {
  const { setCurrentScreen, user } = useApp();
  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <NavBar />
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="text-center max-w-md">
          <div className="text-7xl font-semibold tracking-tight mb-4">404</div>
          <p className="text-ink-muted mb-8">We couldn't find that page.</p>
          <button
            onClick={() => setCurrentScreen(user ? 'dashboard' : 'landing')}
            className="px-6 py-3 bg-white text-black font-medium text-sm hover:bg-gray-200 transition-colors"
          >
            {user ? 'BACK TO DASHBOARD' : 'BACK TO HOME'}
          </button>
        </div>
      </div>
      <Footer />
    </div>
  );
};

// ============================================
// LEGAL / INFO PAGES
// ============================================

const LegalLayout = ({ title, lastUpdated, children }) => (
  <div className="min-h-screen bg-black text-white flex flex-col">
    <NavBar />
    <div className="flex-1">
      <div className="max-w-3xl mx-auto px-8 pt-16 pb-24">
        <h1 className={`text-5xl font-semibold tracking-tight ${lastUpdated ? 'mb-3' : 'mb-12'}`}>{title}</h1>
        {lastUpdated && (
          <p className="text-sm text-ink-faint mb-12">Last updated {lastUpdated}</p>
        )}
        <div className="space-y-8 text-ink-muted leading-relaxed">
          {children}
        </div>
      </div>
    </div>
    <Footer />
  </div>
);

const LegalSection = ({ heading, children }) => (
  <section>
    <h2 className="text-eyebrow text-ink-faint mb-3">{heading}</h2>
    <div className="space-y-3">{children}</div>
  </section>
);

const TermsScreen = () => (
  <LegalLayout title="TERMS OF SERVICE" lastUpdated="April 29, 2026">
    <p>
      These terms govern your use of WhatsInDemand ("the Service"). By creating
      an account or using the Service, you agree to them.
    </p>

    <LegalSection heading="ELIGIBILITY">
      <p>
        You must be at least 18 years old to use the Service. If you don't meet
        this requirement, please don't create an account.
      </p>
    </LegalSection>

    <LegalSection heading="YOUR ACCOUNT">
      <p>
        You're responsible for activity on your account and for keeping your
        credentials secure. Don't share your account or use someone else's.
      </p>
      <p>
        You can delete your account anytime from Settings. We may suspend or
        terminate accounts that violate these terms.
      </p>
    </LegalSection>

    <LegalSection heading="ACCEPTABLE USE">
      <p>
        Don't scrape, mirror, or resell the Service or its data. Don't attempt
        to interfere with its operation, reverse-engineer it, or use it to
        harass or harm others.
      </p>
    </LegalSection>

    <LegalSection heading="THE DATA WE SHOW">
      <p>
        Job market insights are aggregated from publicly available sources.
        We strive for accuracy but make no guarantees of completeness, timeliness,
        or correctness. Don't rely on the Service as the sole basis for major
        career or hiring decisions.
      </p>
    </LegalSection>

    <LegalSection heading="SERVICE AVAILABILITY">
      <p>
        The Service is provided "as is" without warranties of any kind. We may
        change, pause, or discontinue features without notice.
      </p>
    </LegalSection>

    <LegalSection heading="LIMITATION OF LIABILITY">
      <p>
        To the fullest extent permitted by law, WhatsInDemand is not liable for
        indirect, incidental, or consequential damages arising from your use of
        the Service.
      </p>
    </LegalSection>

    <LegalSection heading="CHANGES">
      <p>
        We may update these terms over time. Material changes will be flagged
        on this page (with a new "last updated" date) and, where appropriate,
        via email.
      </p>
    </LegalSection>

    <LegalSection heading="CONTACT">
      <p>
        Questions about these terms?{' '}
        <a href="mailto:thefutureofjobs725@gmail.com" className="text-white underline">
          thefutureofjobs725@gmail.com
        </a>
      </p>
    </LegalSection>
  </LegalLayout>
);

const PrivacyScreen = () => (
  <LegalLayout title="PRIVACY POLICY" lastUpdated="April 29, 2026">
    <p>
      This policy explains what data WhatsInDemand collects, why, and what you
      can do about it. Plain language, no surprises.
    </p>

    <LegalSection heading="WHAT WE COLLECT">
      <p>
        <strong className="text-white">Account data</strong> — your email and a
        hashed password (or a Google account ID if you sign in with Google).
        Optionally, your full name.
      </p>
      <p>
        <strong className="text-white">Career preferences</strong> — the role,
        seniority, location, and skills you choose so we can tailor insights.
      </p>
      <p>
        <strong className="text-white">Resume text</strong> — only when you
        paste or upload it to extract skills. We process it to identify skills
        and discard the raw text after the request completes; we don't store
        your resume.
      </p>
      <p>
        <strong className="text-white">Operational logs</strong> — standard
        request metadata (IP, browser, timestamp) used to operate and secure
        the Service.
      </p>
    </LegalSection>

    <LegalSection heading="HOW WE USE IT">
      <p>
        To run the Service: authenticate you, save your preferences, return
        relevant job-market insights, and send transactional emails (verification,
        password reset, email change confirmation).
      </p>
      <p>
        We don't sell your data. We don't share it for advertising.
      </p>
    </LegalSection>

    <LegalSection heading="THIRD PARTIES WE USE">
      <p>
        <strong className="text-white">Google</strong> — for "Sign in with Google" if you choose it.
      </p>
      <p>
        <strong className="text-white">Resend</strong> — to deliver transactional email.
      </p>
      <p>
        These providers process the minimum data needed for their function
        (your email address, in both cases).
      </p>
    </LegalSection>

    <LegalSection heading="COOKIES & STORAGE">
      <p>
        We store a session token in your browser's localStorage to keep you
        signed in. We don't use tracking cookies or third-party analytics.
      </p>
    </LegalSection>

    <LegalSection heading="YOUR RIGHTS">
      <p>
        From Settings, you can edit your profile, change your email, change
        your password, export a JSON copy of your data, and permanently delete
        your account. Deletion is immediate and removes all associated records.
      </p>
    </LegalSection>

    <LegalSection heading="RETENTION">
      <p>
        Account data is kept until you delete your account. Operational logs
        are kept for a short rolling window for security and debugging.
      </p>
    </LegalSection>

    <LegalSection heading="CHANGES">
      <p>
        We'll update this page if our practices change. The "last updated" date
        at the top reflects the most recent revision.
      </p>
    </LegalSection>

    <LegalSection heading="CONTACT">
      <p>
        Privacy questions or requests?{' '}
        <a href="mailto:thefutureofjobs725@gmail.com" className="text-white underline">
          thefutureofjobs725@gmail.com
        </a>
      </p>
    </LegalSection>
  </LegalLayout>
);

const AboutScreen = () => {
  const { setCurrentScreen } = useApp();
  return (
  <LegalLayout title="ABOUT">
    <p>
      Hi, I'm Henry. Welcome to WhatsInDemand.
    </p>
    <p>
      I built this website because I couldn't stop asking myself: will
      AI take my job?
    </p>
    <p>
      The internet had plenty of answers, and none of them agreed. I
      couldn't tell what was actually true. So I started looking at the
      job market directly. What are companies hiring for right now? Which
      skills are showing up more, which are fading out? Data isn't
      perfect, but it's more reliable than a viral post.
    </p>
    <p>
      That's what this site is. No hype, no doom, no predictions. Just
      what the job market is actually signaling. And it's for anyone
      trying to figure out what their next move should be.
    </p>
    <p>
      Have feedback? The{' '}
      <button
        type="button"
        onClick={() => setCurrentScreen('contact')}
        className="text-white underline hover:text-ink-muted transition-colors"
      >
        contact email
      </button>{' '}
      is real and I read everything. And yes, I'm a real human.
    </p>
  </LegalLayout>
  );
};

const ContactScreen = () => (
  <LegalLayout title="CONTACT">
    <p>
      Found a bug? Have an idea? Just want to talk? Drop me an email at{' '}
      <a href="mailto:thefutureofjobs725@gmail.com" className="text-white underline">
        thefutureofjobs725@gmail.com
      </a>
      .
    </p>
  </LegalLayout>
);

// ============================================
// ACCOUNT SCREEN
// ============================================
const AccountScreen = () => {
  const {
    user,
    setUser,
    setCurrentScreen,
    handleLogout,
    roleData,
    selectedRole,
    baseSeniority,
    baseLocation,
    seniorities,
    userSkills,
  } = useApp();

  const baseSeniorityLabel =
    seniorities?.find(s => s.id === baseSeniority)?.label || baseSeniority || '—';

  const isGoogleAccount = user?.auth_provider === 'google';

  // Inline name editing
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState('');

  // Change-email modal
  const [showEmailModal, setShowEmailModal] = useState(false);

  // Change-password
  const [showPasswordForm, setShowPasswordForm] = useState(false);

  // Verification resend
  const [resendingVerify, setResendingVerify] = useState(false);
  const [verifyMessage, setVerifyMessage] = useState('');

  // Export
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  useEffect(() => {
    if (!user) {
      setCurrentScreen('login');
    }
  }, [user, setCurrentScreen]);

  if (!user) {
    return <LoadingScreen />;
  }

  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : '—';

  const locationsLabel = Array.isArray(baseLocation) && baseLocation.length
    ? baseLocation.join(', ')
    : '—';

  const handleResetPreferences = () => {
    const ok = window.confirm(
      'Reset all saved preferences? Your role, seniority, location, and skills selections will be cleared. You\'ll stay signed in.'
    );
    if (!ok) return;
    clearSession();
    window.location.reload();
  };

  const startEditName = () => {
    setNameDraft(user.full_name || '');
    setNameError('');
    setEditingName(true);
  };

  const saveName = async () => {
    const next = nameDraft.trim();
    if (!next) {
      setNameError('Name cannot be empty');
      return;
    }
    setNameSaving(true);
    setNameError('');
    try {
      const data = await api.updateProfile({ full_name: next });
      if (data.user) setUser(data.user);
      else setUser({ ...user, full_name: next });
      setEditingName(false);
    } catch (err) {
      setNameError(err.message || 'Failed to update name');
    } finally {
      setNameSaving(false);
    }
  };

  const handleResendVerification = async () => {
    setResendingVerify(true);
    setVerifyMessage('');
    try {
      await api.resendVerification();
      setVerifyMessage('Verification email sent. Check your inbox.');
    } catch (err) {
      setVerifyMessage(err.message || 'Failed to send. Try again in a few minutes.');
    } finally {
      setResendingVerify(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportError('');
    try {
      const { blob, filename } = await api.exportData();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white flex">
      <DashboardSidebar />

      <div className="flex-1 ml-64">
        <div className="max-w-3xl mx-auto px-8 pt-8 pb-24">

          <div className="mb-8">
            <button
              onClick={() => roleData ? setCurrentScreen('dashboard') : setCurrentScreen('role-selection')}
              className="text-sm text-ink-muted hover:text-white transition-colors mb-4 flex items-center gap-2"
            >
              ← {roleData ? 'Back to dashboard' : 'Back to start'}
            </button>
            <h1 className="text-5xl font-semibold tracking-tight">
              SETTINGS
            </h1>
          </div>

          <div className="space-y-6">

            {/* Profile */}
            <section className="p-6 bg-surface border border-line">
              <div className="text-eyebrow text-ink-faint mb-4">PROFILE</div>
              <div className="flex items-center gap-4 mb-6">
                <div className="w-16 h-16 bg-white/10 flex items-center justify-center">
                  <span className="text-2xl font-medium">
                    {user.full_name?.charAt(0) || user.email?.charAt(0) || 'U'}
                  </span>
                </div>
                <div>
                  <h2 className="text-xl font-medium">{user.full_name || 'User'}</h2>
                  <p className="text-ink-muted">{user.email}</p>
                </div>
              </div>

              <div>
                <div className="py-3 border-b border-line">
                  <div className="flex justify-between items-center">
                    <span className="text-ink-muted">Full Name</span>
                    {editingName ? (
                      <div className="flex items-center gap-2">
                        <input
                          autoFocus
                          value={nameDraft}
                          onChange={(e) => setNameDraft(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') setEditingName(false); }}
                          disabled={nameSaving}
                          className="px-3 py-1 bg-black border border-line-strong text-sm focus:outline-none focus:border-white"
                        />
                        <button
                          onClick={saveName}
                          disabled={nameSaving}
                          className="text-sm px-3 py-1 bg-white text-black hover:bg-white/90 disabled:opacity-50"
                        >
                          {nameSaving ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          onClick={() => setEditingName(false)}
                          disabled={nameSaving}
                          className="text-sm px-3 py-1 border border-line-strong hover:bg-white/5"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-3">
                        <span className="font-medium">{user.full_name || '—'}</span>
                        <button
                          onClick={startEditName}
                          className="text-sm text-ink-muted hover:text-white transition-colors"
                        >
                          Edit
                        </button>
                      </div>
                    )}
                  </div>
                  {nameError && <div className="text-xs text-red-400 mt-2">{nameError}</div>}
                </div>
                <div className="flex justify-between items-center py-3 border-b border-line">
                  <span className="text-ink-muted">Email</span>
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{user.email}</span>
                    {!isGoogleAccount && (
                      <button
                        onClick={() => setShowEmailModal(true)}
                        className="text-sm text-ink-muted hover:text-white transition-colors"
                      >
                        Change
                      </button>
                    )}
                  </div>
                </div>
                {user.pending_email && (
                  <div className="flex justify-between items-center py-3 border-b border-line">
                    <span className="text-ink-muted">Pending email</span>
                    <span className="text-sm text-ink-muted italic">
                      {user.pending_email} (awaiting confirmation)
                    </span>
                  </div>
                )}
                <div className="flex justify-between py-3">
                  <span className="text-ink-muted">Member since</span>
                  <span className="font-medium">{memberSince}</span>
                </div>
              </div>
            </section>

            {/* Career preferences */}
            <section className="p-6 bg-surface border border-line">
              <div className="flex items-center justify-between mb-4">
                <div className="text-eyebrow text-ink-faint">CAREER PREFERENCES</div>
                <button
                  onClick={() => setCurrentScreen('role-selection')}
                  className="text-sm text-ink-muted hover:text-white transition-colors"
                >
                  Change role →
                </button>
              </div>

              <div>
                <div className="flex justify-between items-center py-3 border-b border-line">
                  <span className="text-ink-muted">Target role</span>
                  <span className="font-medium">{selectedRole || '—'}</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-line">
                  <span className="text-ink-muted">Seniority</span>
                  <span className="font-medium">{baseSeniorityLabel}</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-line">
                  <span className="text-ink-muted">Location</span>
                  <span className="font-medium text-right max-w-xs truncate" title={locationsLabel}>
                    {locationsLabel}
                  </span>
                </div>
                <div className="flex justify-between items-center py-3">
                  <span className="text-ink-muted">Your skills</span>
                  <div className="flex items-center gap-3">
                    <span className="font-medium">
                      {userSkills?.length || 0} {userSkills?.length === 1 ? 'skill' : 'skills'}
                    </span>
                    <button
                      onClick={() => setCurrentScreen('skills-input')}
                      disabled={!selectedRole || !roleData}
                      className="text-sm text-ink-muted hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Edit →
                    </button>
                  </div>
                </div>
              </div>
            </section>

            {/* Security */}
            <section className="p-6 bg-surface border border-line">
              <div className="text-eyebrow text-ink-faint mb-4">SECURITY</div>

              <div>
                <div className="py-3 border-b border-line">
                  <div className="flex justify-between items-center">
                    <span className="text-ink-muted">Password</span>
                    {isGoogleAccount ? (
                      <span className="text-sm text-ink-muted">Signed in via Google</span>
                    ) : (
                      <button
                        onClick={() => setShowPasswordForm(v => !v)}
                        className="text-sm text-ink-muted hover:text-white transition-colors"
                      >
                        {showPasswordForm ? 'Cancel' : 'Change password'}
                      </button>
                    )}
                  </div>
                  {showPasswordForm && !isGoogleAccount && (
                    <ChangePasswordForm onDone={() => setShowPasswordForm(false)} />
                  )}
                </div>

                <div className="py-3">
                  <div className="flex justify-between items-center">
                    <span className="text-ink-muted">Email verification</span>
                    <div className="flex items-center gap-3">
                      {user.email_verified ? (
                        <span className="text-xs px-2 py-1 bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                          Verified
                        </span>
                      ) : (
                        <>
                          <span className="text-xs px-2 py-1 bg-yellow-500/15 text-yellow-300 border border-yellow-500/30">
                            Unverified
                          </span>
                          <button
                            onClick={handleResendVerification}
                            disabled={resendingVerify}
                            className="text-sm text-ink-muted hover:text-white transition-colors disabled:opacity-50"
                          >
                            {resendingVerify ? 'Sending…' : 'Send verification email'}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  {verifyMessage && (
                    <div className="text-xs text-ink-muted mt-2">{verifyMessage}</div>
                  )}
                </div>
              </div>
            </section>

            {/* Data */}
            <section className="p-6 bg-surface border border-line">
              <div className="text-eyebrow text-ink-faint mb-4">DATA</div>

              <div className="flex items-start justify-between gap-6 py-3 border-b border-line">
                <div>
                  <div className="font-medium mb-1">Reset preferences</div>
                  <div className="text-sm text-ink-muted">
                    Clear your saved role, seniority, location, and skills. Your account stays intact.
                  </div>
                </div>
                <button
                  onClick={handleResetPreferences}
                  className="shrink-0 px-4 py-2 border border-line-strong text-sm hover:bg-white/5 transition-colors"
                >
                  Reset
                </button>
              </div>

              <div className="flex items-start justify-between gap-6 pt-4">
                <div>
                  <div className="font-medium mb-1">Export my data</div>
                  <div className="text-sm text-ink-muted">
                    Download a JSON copy of your account, preferences, and saved skills.
                  </div>
                  {exportError && (
                    <div className="text-xs text-red-400 mt-2">{exportError}</div>
                  )}
                </div>
                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="shrink-0 px-4 py-2 border border-line-strong text-sm hover:bg-white/5 transition-colors disabled:opacity-50"
                >
                  {exporting ? 'Preparing…' : 'Export'}
                </button>
              </div>
            </section>

            {/* Danger zone */}
            <section className="p-6 bg-surface border border-red-500/40">
              <div className="flex items-start justify-between gap-6">
                <div>
                  <div className="font-medium mb-1">Delete account</div>
                  <div className="text-sm text-ink-muted">
                    Permanently delete your account and all associated data. This cannot be undone.
                  </div>
                </div>
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="shrink-0 px-4 py-2 border border-red-500/50 text-red-400 text-sm hover:bg-red-500/10 transition-colors"
                >
                  Delete
                </button>
              </div>
            </section>

          </div>
        </div>

        <Footer />
      </div>

      {showEmailModal && (
        <ChangeEmailModal
          onClose={() => setShowEmailModal(false)}
          onSubmitted={() => {
            setShowEmailModal(false);
          }}
        />
      )}

      {showDeleteModal && (
        <DeleteAccountModal
          isGoogleAccount={isGoogleAccount}
          onClose={() => setShowDeleteModal(false)}
          onDeleted={() => {
            setShowDeleteModal(false);
            handleLogout();
          }}
        />
      )}
    </div>
  );
};

const ChangePasswordForm = ({ onDone }) => {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (next.length < 8) {
      setError('New password must be at least 8 characters');
      return;
    }
    if (next !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setSaving(true);
    try {
      await api.changePassword(current, next);
      setSuccess('Password updated.');
      setCurrent(''); setNext(''); setConfirm('');
      setTimeout(() => { onDone?.(); }, 800);
    } catch (err) {
      setError(err.message || 'Failed to change password');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-4 space-y-3">
      <input
        type="password"
        placeholder="Current password"
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        className="w-full px-3 py-2 bg-black border border-line-strong text-sm focus:outline-none focus:border-white"
      />
      <input
        type="password"
        placeholder="New password (min 8 characters)"
        value={next}
        onChange={(e) => setNext(e.target.value)}
        className="w-full px-3 py-2 bg-black border border-line-strong text-sm focus:outline-none focus:border-white"
      />
      <input
        type="password"
        placeholder="Confirm new password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        className="w-full px-3 py-2 bg-black border border-line-strong text-sm focus:outline-none focus:border-white"
      />
      {error && <div className="text-xs text-red-400">{error}</div>}
      {success && <div className="text-xs text-emerald-400">{success}</div>}
      <button
        type="submit"
        disabled={saving || !current || !next || !confirm}
        className="px-4 py-2 bg-white text-black text-sm hover:bg-white/90 disabled:opacity-50"
      >
        {saving ? 'Updating…' : 'Update password'}
      </button>
    </form>
  );
};

const ChangeEmailModal = ({ onClose, onSubmitted }) => {
  const [newEmail, setNewEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await api.requestEmailChange(newEmail.trim(), password);
      setSent(true);
      setTimeout(() => { onSubmitted?.(); }, 1500);
    } catch (err) {
      setError(err.message || 'Failed to send confirmation');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface border border-line p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-xl font-medium mb-2">Change email</h3>
        <p className="text-sm text-ink-muted mb-4">
          We'll send a confirmation link to your new address. Your email won't change until you click it.
        </p>
        {sent ? (
          <div className="text-sm text-emerald-400 mb-4">
            Confirmation sent to {newEmail}. Check your inbox.
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <input
              type="email"
              placeholder="New email"
              required
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              className="w-full px-3 py-2 bg-black border border-line-strong text-sm focus:outline-none focus:border-white"
            />
            <input
              type="password"
              placeholder="Current password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-black border border-line-strong text-sm focus:outline-none focus:border-white"
            />
            {error && <div className="text-xs text-red-400">{error}</div>}
            <div className="flex gap-2 justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-line-strong text-sm hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !newEmail || !password}
                className="px-4 py-2 bg-white text-black text-sm hover:bg-white/90 disabled:opacity-50"
              >
                {submitting ? 'Sending…' : 'Send confirmation'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

const DeleteAccountModal = ({ isGoogleAccount, onClose, onDeleted }) => {
  const [password, setPassword] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const canSubmit = isGoogleAccount ? confirmText === 'DELETE' : password.length > 0;

  const submit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError('');
    setSubmitting(true);
    try {
      const body = isGoogleAccount ? { confirm: 'DELETE' } : { password };
      await api.deleteAccount(body);
      onDeleted?.();
    } catch (err) {
      setError(err.message || 'Failed to delete account');
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface border border-red-500/50 p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-xl font-medium mb-2 text-red-400">Delete account</h3>
        <p className="text-sm text-ink-muted mb-4">
          This permanently deletes your account, saved preferences, and skills. This action cannot be undone.
        </p>
        <form onSubmit={submit} className="space-y-3">
          {isGoogleAccount ? (
            <>
              <p className="text-sm">Type <span className="font-mono text-white">DELETE</span> to confirm.</p>
              <input
                type="text"
                placeholder="DELETE"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                className="w-full px-3 py-2 bg-black border border-line-strong text-sm focus:outline-none focus:border-red-500"
              />
            </>
          ) : (
            <>
              <p className="text-sm">Enter your password to confirm.</p>
              <input
                type="password"
                placeholder="Current password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 bg-black border border-line-strong text-sm focus:outline-none focus:border-red-500"
              />
            </>
          )}
          {error && <div className="text-xs text-red-400">{error}</div>}
          <div className="flex gap-2 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-line-strong text-sm hover:bg-white/5"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit || submitting}
              className="px-4 py-2 bg-red-500 text-white text-sm hover:bg-red-500/90 disabled:opacity-50"
            >
              {submitting ? 'Deleting…' : 'Delete my account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ============================================
// MAIN APP ROUTER
// ============================================
// Syncs URL <-> currentScreen and enforces deep-link guards.
const ScreenSync = () => {
  const {
    currentScreen, setCurrentScreen,
    user, roleData, selectedRole, initialLoading,
  } = useApp();
  const location = useLocation();
  const navigate = useNavigate();

  // URL -> state (back/forward, deep link)
  useEffect(() => {
    const screen = PATH_TO_SCREEN[location.pathname];
    if (screen && screen !== currentScreen) {
      setCurrentScreen(screen);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // state -> URL
  useEffect(() => {
    const path = SCREEN_TO_PATH[currentScreen];
    if (path && path !== location.pathname) {
      navigate(path);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentScreen]);

  // Scroll to top on screen change
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [currentScreen]);

  // Deep-link guards (wait until auth check finishes)
  useEffect(() => {
    if (initialLoading) return;
    if (currentScreen === 'dashboard' && !roleData) {
      setCurrentScreen(user ? 'role-selection' : 'landing');
    } else if (currentScreen === 'skills-input' && (!selectedRole || !roleData)) {
      setCurrentScreen(user ? 'role-selection' : 'landing');
    } else if (currentScreen === 'account' && !user) {
      setCurrentScreen('login');
    }
  }, [initialLoading, currentScreen, user, roleData, selectedRole, setCurrentScreen]);

  return null;
};

const PAGE_TITLES = {
  '/': 'WhatsInDemand — See which skills are in demand',
  '/login': 'Sign in · WhatsInDemand',
  '/signup': 'Create your account · WhatsInDemand',
  '/forgot-password': 'Forgot password · WhatsInDemand',
  '/reset-password': 'Reset password · WhatsInDemand',
  '/verify-email': 'Verify your email · WhatsInDemand',
  '/start': 'Pick your role · WhatsInDemand',
  '/skills-input': 'Your skills · WhatsInDemand',
  '/dashboard': 'Dashboard · WhatsInDemand',
  '/account': 'Account · WhatsInDemand',
  '/about': 'About · WhatsInDemand',
  '/terms': 'Terms of Service · WhatsInDemand',
  '/privacy': 'Privacy Policy · WhatsInDemand',
  '/contact': 'Contact · WhatsInDemand',
};

const PageTitleSync = () => {
  const location = useLocation();
  useEffect(() => {
    document.title = PAGE_TITLES[location.pathname] || 'Page not found · WhatsInDemand';
  }, [location.pathname]);
  return null;
};

const AppRouter = () => {
  const { initialLoading } = useApp();

  if (initialLoading) {
    return <InitialLoadingScreen />;
  }

  return (
    <>
      <PageTitleSync />
      <ScreenSync />
      <Routes>
        <Route path="/" element={<LandingScreen />} />
        <Route path="/login" element={<LoginScreen />} />
        <Route path="/signup" element={<SignupScreen />} />
        <Route path="/forgot-password" element={<ForgotPasswordScreen />} />
        <Route path="/reset-password" element={<ResetPasswordScreen />} />
        <Route path="/verify-email" element={<VerifyEmailScreen />} />
        <Route path="/start" element={<RoleSelectionScreen />} />
        <Route path="/skills-input" element={<SkillsInputScreen />} />
        <Route path="/dashboard" element={<DashboardScreen />} />
        <Route path="/account" element={<AccountScreen />} />
        <Route path="/about" element={<AboutScreen />} />
        <Route path="/terms" element={<TermsScreen />} />
        <Route path="/privacy" element={<PrivacyScreen />} />
        <Route path="/contact" element={<ContactScreen />} />
        <Route path="*" element={<NotFoundScreen />} />
      </Routes>
    </>
  );
};

// ============================================
// MAIN APP COMPONENT
// ============================================
const WhatsInDemand = () => {
  return (
    <BrowserRouter>
      <AppProvider>
        <AppRouter />
      </AppProvider>
    </BrowserRouter>
  );
};

export default WhatsInDemand;