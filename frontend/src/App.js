// App.js - WhatsInDemand Career Intelligence App

import React, { useState, useEffect, useRef, createContext, useContext, useCallback, useMemo } from 'react';
import { 
  ArrowRight, Search, ChevronDown, X, Filter, 
  Zap, Layers, ExternalLink 
} from 'lucide-react';
import api from './services/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';



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

const AppProvider = ({ children }) => {
  // Navigation
  const [currentScreen, setCurrentScreen] = useState('landing');
  
  // User & Auth
  const [user, setUser] = useState(null);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupFullName, setSignupFullName] = useState('');
  
  // Role Selection
  const [selectedRole, setSelectedRole] = useState('');
  const [roleSearchQuery, setRoleSearchQuery] = useState('');
  const [showRoleDropdown, setShowRoleDropdown] = useState(false);
  const [selectedSeniority, setSelectedSeniority] = useState('All');
  const [selectedLocation, setSelectedLocation] = useState(['All']);
  
  // Dashboard Filters (inside dashboard)
  const [industries, setIndustries] = useState([]);
  const [selectedIndustries, setSelectedIndustries] = useState(['All']);
  const [selectedCompanies, setSelectedCompanies] = useState(['All']);
  const [appliedSeniority, setAppliedSeniority] = useState('All');
  const [appliedLocation, setAppliedLocation] = useState(['All']);
  const [activeTab, setActiveTab] = useState('overview');
  
  // Data
  const [allRoles, setAllRoles] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [roleData, setRoleData] = useState(null);
  const [alternativeRoles, setAlternativeRoles] = useState([]);
  
  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [initialLoading, setInitialLoading] = useState(true);

  useEffect(() => {
    console.log('selectedLocation changed:', selectedLocation);
  }, [selectedLocation]);

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
        
        // If we have cached analysis data, use it
        if (session.analysis) {
          setRoleData(session.analysis);
          setCurrentScreen('dashboard');
          setAppliedSeniority(session.seniority_level || '');
          setAppliedLocation(parsedLocation);
          return true;
        }
        
        // Otherwise just go to role selection with pre-filled values
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
      
      // Try to restore last session
      await restoreLastSession();
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
        setCurrentScreen('dashboard');
        setActiveTab('overview');
        setAppliedSeniority(selectedSeniority);
        setAppliedLocation(selectedLocation);
        
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
  }, [selectedRole, selectedSeniority, selectedLocation, selectedIndustries, selectedCompanies, user]);

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
  }, [selectedSeniority, selectedLocation, selectedIndustries, selectedCompanies, user]);

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
    api.logout();
    setUser(null);
    setRoleData(null);
    setSelectedRole('');
    setRoleSearchQuery('');
    setSelectedSeniority('All');
    setSelectedIndustries(['All']);
    setSelectedCompanies(['All']);
    setAppliedSeniority('All');
    setAppliedLocation(['All']);
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
    <nav className="px-8 py-6 border-b border-white/10">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <button 
          onClick={() => setCurrentScreen('landing')}
          className="text-lg font-bold tracking-widest hover:text-gray-400 transition-colors"
        >
          WhatsInDemand
        </button>
        
        {user ? (
          <button 
            onClick={handleLogout}
            className="text-md font-bold hover:text-gray-400 transition-colors"
          >
            SIGN OUT
          </button>
        ) : (
          <button 
            onClick={() => setCurrentScreen('login')}
            className="text-md font-bold hover:text-gray-400 transition-colors"
          >
            SIGN IN
          </button>
        )}
      </div>
    </nav>
  );
};

const Footer = () => (
  <footer className="border-t border-white/10 mt-auto">
    <div className="max-w-7xl mx-auto px-8 py-6 text-center text-gray-500 text-xs">
      © {new Date().getFullYear()} WhatsInDemand. All rights reserved.
    </div>
  </footer>
);

const ErrorMessage = ({ error, onClose }) => {
  if (!error) return null;
  
  return (
    <div className="mb-4 p-4 bg-red-500/20 border border-red-500 text-red-400">
      <strong>Error:</strong> {error}
      <button 
        onClick={onClose}
        className="float-right text-red-400 hover:text-red-300"
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
        className={`px-4 py-2 bg-white/5 border text-white text-sm focus:outline-none cursor-pointer flex items-center gap-2 min-w-[160px] transition-colors ${
          isOpen ? 'border-white' : 'border-white/20 hover:border-white/40'
        }`}
      >
        <span className="flex-1 text-left truncate">{getDisplayText()}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-zinc-900 border border-white/20 z-30 shadow-xl max-h-72 overflow-y-auto">
          {/* All option */}
          <label className="flex items-center gap-3 px-4 py-3 hover:bg-white/5 cursor-pointer border-b border-white/10">
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
                className="flex items-center gap-3 px-4 py-3 hover:bg-white/5 cursor-pointer"
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
            <div className="px-4 py-6 text-center text-gray-500 text-sm">
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
        className={`px-4 py-2 bg-white/5 border text-white text-sm focus:outline-none cursor-pointer flex items-center gap-2 min-w-[160px] transition-colors ${
          isOpen ? 'border-white' : 'border-white/20 hover:border-white/40'
        }`}
      >
        <span className="flex-1 text-left truncate">{getDisplayText()}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-zinc-900 border border-white/20 z-30 shadow-xl max-h-[320px] overflow-y-auto">
          {/* All Locations */}
          <label className="flex items-center gap-3 px-4 py-3 hover:bg-white/5 cursor-pointer border-b border-white/10">
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
              <label className="flex items-center gap-3 px-4 py-2 bg-zinc-950 hover:bg-white/5 cursor-pointer sticky top-0">
                <input
                  type="checkbox"
                  checked={isRegionFullySelected(region.region)}
                  ref={(el) => {
                    if (el) el.indeterminate = isRegionPartiallySelected(region.region);
                  }}
                  onChange={() => handleRegionClick(region.region)}
                  className="w-4 h-4 accent-white"
                />
                <span className="text-xs font-bold text-gray-400 tracking-wider">
                  {region.region.toUpperCase()}
                </span>
              </label>
              
              {region.countries.map((country) => (
                <label
                  key={country.value}
                  className="flex items-center gap-3 px-4 py-2 pl-8 hover:bg-white/5 cursor-pointer"
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
        className={`px-4 py-2 bg-white/5 border text-white text-sm focus:outline-none cursor-pointer flex items-center gap-2 min-w-[140px] transition-colors ${
          isOpen ? 'border-white' : 'border-white/20 hover:border-white/40'
        }`}
      >
        <span className="flex-1 text-left truncate text-white">{displayText}</span>
        <ChevronDown className={`w-4 h-4 text-white transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-full min-w-[180px] bg-zinc-900 border border-white/20 z-30 shadow-xl max-h-64 overflow-y-auto">
          {options.map((option, idx) => {
            const optValue = getOptionValue(option);
            const optLabel = getOptionLabel(option);
            const isSelected = optValue === value;
            
            return (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelect(optValue)}
                className={`w-full px-4 py-2 text-left text-sm hover:bg-white/5 transition-colors flex items-center justify-between ${
                  isSelected ? 'bg-white/10 text-white' : 'text-white'
                }`}
              >
                <span>{optLabel}</span>
                {isSelected && <span className="text-xs text-gray-500">✓</span>}
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
const GoogleSignInButton = ({ onSuccess, onError, text = "CONTINUE WITH GOOGLE" }) => {
  const buttonRef = useRef(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const initGoogle = () => {
      if (!window.google?.accounts?.id) return;

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
        ux_mode: 'popup',  // Force popup mode
        use_fedcm_for_prompt: false,  // Disable FedCM for now
      });

      // Render the actual Google button
      if (buttonRef.current) {
        window.google.accounts.id.renderButton(buttonRef.current, {
          type: 'standard',
          theme: 'filled_black',
          size: 'large',
          text: 'continue_with',
          shape: 'rectangular',
          width: buttonRef.current.offsetWidth,
        });
      }
    };

    if (window.google?.accounts?.id) {
      initGoogle();
    } else {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = initGoogle;
      document.body.appendChild(script);
    }
  }, [onSuccess, onError]);

  if (isLoading) {
    return (
      <div className="w-full px-6 py-4 bg-white/20 text-gray-400 font-bold text-sm tracking-wide flex items-center justify-center gap-3">
        <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin"></div>
        SIGNING IN...
      </div>
    );
  }

  return (
    <div 
      ref={buttonRef} 
      className="w-full flex justify-center [&>div]:w-full [&_iframe]:w-full"
      style={{ minHeight: '44px' }}
    />
  );
};

// ============================================
// NO RESULTS MESSAGE
// ============================================

const NoResultsMessage = ({ onClearFilters, loading }) => (
  <div className="p-12 bg-white/5 border border-white/10 text-center">
    <div className="text-5xl mb-4">🔍</div>
    <h3 className="text-2xl font-black mb-2">No Jobs Found</h3>
    <p className="text-gray-400 mb-6 max-w-md mx-auto">
      No jobs match your current filter combination. Try adjusting your filters or clearing them to see all results.
    </p>
    <button
      onClick={onClearFilters}
      disabled={loading}
      className={`px-6 py-3 font-bold transition-colors ${
        loading
          ? 'bg-white/20 text-gray-400 cursor-not-allowed'
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
          <h1 className="text-5xl sm:text-7xl md:text-8xl font-black mb-8 sm:mb-12 leading-none tracking-tight">
            YOUR ROLE <br />
            IS CHANGING
          </h1>

          <p className="text-lg sm:text-xl text-gray-400 mb-6 max-w-2xl leading-relaxed">
            AI is reshaping every profession. <br className="hidden sm:block" /> 
            Some skills are fading, while others are exploding in demand.
          </p>

          <p className="text-lg sm:text-xl text-gray-400 mb-6 max-w-2xl leading-relaxed" style={{ textWrap: 'balance' }}>
            We track thousands of job postings in real time to show you what's in demand, what's fading, and where to focus next.
          </p>
            
          <p className="text-lg sm:text-xl text-gray-400 mb-8 sm:mb-12 max-w-2xl leading-relaxed">
            No hype. Just data.
          </p>

          <div className="inline-flex flex-col items-start gap-3">
            <button 
              onClick={() => setCurrentScreen('role-selection')}
              className="px-8 sm:px-12 py-4 bg-white text-black font-bold text-lg sm:text-xl hover:bg-gray-200 transition-colors"
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
        <div className="max-w-md mx-auto px-6 pt-20 pb-24">
          <h1 className="text-4xl font-black mb-8 tracking-tight">
            SIGN IN
          </h1>

          <ErrorMessage error={error} onClose={() => setError(null)} />

          {/* Google Sign-In Button */}
          <GoogleSignInButton
            onSuccess={handleGoogleSuccess}
            onError={handleGoogleError}
          />

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/20"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-black text-gray-500 uppercase tracking-wider">Or continue with email</span>
            </div>
          </div>

          <form onSubmit={onSubmit}>
            <div className="space-y-3 mb-6">
              <input
                type="email"
                placeholder="Email address"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/20 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="email"
              />
              <input
                type="password"
                placeholder="Password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/20 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !loginEmail || !loginPassword}
              className={`w-full py-3 font-bold text-sm tracking-wide transition-colors ${
                !loading && loginEmail && loginPassword
                  ? 'bg-white text-black hover:bg-gray-200'
                  : 'bg-white/10 text-gray-600 cursor-not-allowed'
              }`}
            >
              {loading ? 'SIGNING IN...' : 'SIGN IN'}
            </button>
          </form>

          <div className="text-center text-gray-400 text-sm mt-6">
            Don't have an account?{' '}
            <button 
              onClick={() => setCurrentScreen('role-selection')}
              className="text-white underline hover:text-gray-300"
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
            <h1 className="text-5xl md:text-6xl font-black mb-6 tracking-tight">
              WHAT'S YOUR ROLE?
            </h1>
            <p className="text-xl text-gray-400">
              See what skills are in demand and how the role is evolving.
            </p>
          </div>

          <ErrorMessage error={error} onClose={() => setError(null)} />
    
          {/* Role Search */}
          <div className="mb-6">
            <label className="block text-sm text-gray-500 mb-2 tracking-wider font-bold">
              ROLE TITLE
            </label>
            <div className="relative" ref={dropdownRef}>
              <Search className="absolute left-5 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500 pointer-events-none" />
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
                className={`w-full pl-14 pr-12 py-5 bg-white/5 border-2 text-white placeholder-gray-500 text-lg focus:outline-none transition-colors ${
                  selectedRole 
                    ? 'border-white bg-white/10' 
                    : 'border-white/20 focus:border-white'
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
                  className="absolute right-5 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              ) : (
                <ChevronDown className={`absolute right-5 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500 pointer-events-none transition-transform ${showRoleDropdown ? 'rotate-180' : ''}`} />
              )}

              {/* Dropdown - only show when no role selected */}
              {showRoleDropdown && filteredRoles.length > 0 && !selectedRole && (
                <div className="absolute w-full mt-2 bg-zinc-900 border-2 border-white/20 max-h-72 overflow-y-auto z-20">
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
                          <span className="text-sm text-gray-500">{jobCount} jobs</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            
            {/* Helper text when role is selected */}
            {selectedRole && (
              <div className="mt-2 text-sm text-gray-500">
                Click the X to change your selection
              </div>
            )}
          </div>

          {/* Seniority Selection */}
          <div className="mb-6">
            <label className="block text-sm text-gray-500 mb-2 tracking-wider font-bold">
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
                      : 'border-white/20 hover:border-white/40'
                  }`}
                >
                  <div className="font-bold text-sm">{level.label}</div>
                  <div className="text-xs text-gray-500">{level.subtitle}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Location Selection */}
          <div className="mb-10">
            <label className="block text-sm text-gray-500 mb-2 tracking-wider font-bold">
              LOCATION <span className="text-gray-600"></span>
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
            className={`w-full py-5 font-bold text-xl transition-colors flex items-center justify-center gap-3 ${
              canProceed && !loading
                ? 'bg-white text-black hover:bg-gray-200'
                : 'bg-white/10 text-gray-600 cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin"></div>
                ANALYZING...
              </>
            ) : (
              <>
                EXPLORE THIS ROLE
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>

          <p className="text-center text-gray-500 text-sm mt-4">
            Free to explore (Beta)
          </p>
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
            <h1 className="text-4xl font-black mb-3 tracking-tight">
              CREATE ACCOUNT
            </h1>
            <p className="text-gray-400 text-sm">
              Sign up to explore <span className="text-white font-semibold">{selectedRole}</span>
              {seniorityLabel && <span className="text-gray-500"> • {seniorityLabel}</span>}
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
              <div className="w-full border-t border-white/20"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-black text-gray-500 uppercase tracking-wider">Or continue with email</span>
            </div>
          </div>

          <form onSubmit={onSubmit}>
            <div className="space-y-3 mb-4">
              <input
                type="text"
                placeholder="Full name"
                value={signupFullName}
                onChange={(e) => setSignupFullName(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/20 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="name"
              />
              <input
                type="email"
                placeholder="Email address"
                value={signupEmail}
                onChange={(e) => setSignupEmail(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/20 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="email"
              />
              <input
                type="password"
                placeholder="Password (min 8 characters)"
                value={signupPassword}
                onChange={(e) => setSignupPassword(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/20 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors"
                autoComplete="new-password"
              />
            </div>

            <div className="mb-5 p-3 bg-white/5 border-l-2 border-white/40">
              <p className="text-xs text-gray-400">
                By signing up, you agree to our{' '}
                <a href="#" className="text-white underline hover:text-gray-300">Terms of Service</a>
                {' '}and{' '}
                <a href="#" className="text-white underline hover:text-gray-300">Privacy Policy</a>
              </p>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setCurrentScreen('role-selection')}
                className="px-5 py-3 border border-white/20 text-sm font-bold hover:bg-white/5 transition-colors"
              >
                BACK
              </button>
              <button
                type="submit"
                disabled={loading || !signupEmail || !signupPassword || !signupFullName}
                className={`flex-1 py-3 font-bold text-sm tracking-wide transition-colors ${
                  !loading && signupEmail && signupPassword && signupFullName
                    ? 'bg-white text-black hover:bg-gray-200'
                    : 'bg-white/10 text-gray-600 cursor-not-allowed'
                }`}
              >
                {loading ? 'CREATING ACCOUNT...' : 'CREATE ACCOUNT'}
              </button>
            </div>
          </form>

          <div className="text-center text-gray-400 text-sm mt-6">
            Already have an account?{' '}
            <button 
              onClick={() => setCurrentScreen('login')}
              className="text-white underline hover:text-gray-300"
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
      <div className="flex items-center justify-between p-4 border-b border-white/10 bg-zinc-950">
        <button 
          onClick={() => setCurrentScreen('landing')}
          className="text-sm font-bold tracking-widest"
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
      <div className="flex border-b border-white/10 bg-zinc-950 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 min-w-max px-4 py-3 text-xs font-bold tracking-wider transition-colors ${
              activeTab === tab.id
                ? 'text-white border-b-2 border-white'
                : 'text-gray-500'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Dropdown Menu */}
      {menuOpen && (
        <div className="absolute top-14 right-4 z-50 w-64 bg-zinc-900 border border-white/10 shadow-xl">
          {user && (
            <div className="p-4 border-b border-white/10">
              <div className="font-bold text-sm">{user.full_name || 'User'}</div>
              <div className="text-xs text-gray-500">{user.email}</div>
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
              Explore New Role
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
              className="w-full px-4 py-3 text-left text-sm text-gray-400 hover:bg-white/10 transition-colors"
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
    setCurrentScreen
  } = useApp();

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
          
          {/* Header - Responsive */}
          <div className="mb-6 lg:mb-8">
            <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm text-gray-500 mb-2">
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
            <h1 className="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-black tracking-tight mb-3 lg:mb-4">
              {selectedRole?.toUpperCase()}
            </h1>
            <div className="text-base lg:text-lg text-gray-400">
              Based on <span className="text-white font-bold">
                {roleData?.total_jobs_analyzed?.toLocaleString() || '0'}
              </span> job postings
              {roleData?.company_count > 0 && (
                <span className="text-gray-500">
                  {' '}from {roleData.company_count} {roleData.company_count === 1 ? 'company' : 'companies'}
                </span>
              )}
            </div>
          </div>

          {/* Filter Bar - Responsive */}
          <div className="mb-6 lg:mb-8 p-3 lg:p-4 bg-white/5 border border-white/10">
            <div className="flex flex-wrap items-center gap-2 lg:gap-4">
              <div className="flex items-center gap-2 text-xs lg:text-sm text-gray-400">
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
                  className="px-2 lg:px-3 py-2 text-xs lg:text-sm text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
                >
                  <X className="w-3 h-3" />
                  <span className="hidden sm:inline">Clear</span>
                </button>
              )}

              {/* Loading indicator */}
              {loading && (
                <div className="ml-auto flex items-center gap-2 text-xs lg:text-sm text-gray-400">
                  <div className="w-4 h-4 border-2 border-gray-600 border-t-white rounded-full animate-spin"></div>
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
    { id: 'overview', label: 'OVERVIEW', description: 'Market snapshot' },
    { id: 'employers', label: 'COMPANIES', description: 'Who\'s hiring' },
    { id: 'skills', label: 'SKILLS IN DEMAND', description: 'Demand breakdown' },
    { id: 'paths', label: 'ALTERNATIVE ROLES', description: 'Adjacent roles' },
  ];

  return (
    <div className="hidden lg:flex w-64 border-r border-white/10 flex-col fixed h-screen bg-zinc-950">
      {/* Logo & User */}
      <div className="p-6 border-b border-white/10">
        <button 
          onClick={() => setCurrentScreen('landing')}
          className="text-sm font-bold tracking-widest hover:text-gray-400 transition-colors mb-6 block"
        >
          WhatsInDemand
        </button>
        
        {user && (
          <button
            onClick={() => setCurrentScreen('account')}
            className="w-full flex items-center gap-3 p-2 -m-2 rounded hover:bg-white/5 transition-colors text-left"
          >
            <div className="w-10 h-10 bg-white/10 rounded-full flex items-center justify-center">
              <span className="text-lg font-bold">
                {user.full_name?.charAt(0) || user.email?.charAt(0) || 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-bold text-sm truncate">{user.full_name || 'User'}</div>
              <div className="text-xs text-gray-500 truncate">{user.email}</div>
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
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <div className="text-sm font-bold tracking-wider">{tab.label}</div>
              <div className="text-xs text-gray-500">{tab.description}</div>
            </button>
          ))}
        </div>
      </nav>

      {/* Bottom Actions */}
      <div className="p-4 border-t border-white/10 space-y-2">
        <button 
          onClick={() => setCurrentScreen('role-selection')}
          className="w-full px-4 py-3 bg-white text-black font-bold text-sm hover:bg-gray-200 transition-colors"
        >
          EXPLORE NEW ROLE
        </button>
        <button 
          onClick={handleLogout}
          className="w-full px-4 py-3 text-left text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
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
const OverviewTab = () => {
  const {
    roleData,
    selectedRole,
    setActiveTab,
  } = useApp();

  const skills = roleData?.skills || [];
  const topCompanies = roleData?.top_companies || [];
  const totalJobs = roleData?.total_jobs_analyzed || 0;
  const companyCount = roleData?.company_count || 0;
  const marketTrend = roleData?.market_trend;
  const salaryInfo = roleData?.salary_info;
  const trendData = roleData?.trend_data || [];

  // Derived data
  const skillBreadth = skills.length;
  const tableStakesCount = skills.filter(s => s.demand >= 50).length;

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

  // Format date for chart
  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short' }); 
  };

  // Custom tooltip for chart
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const date = new Date(label);
      const monthYear = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
      return (
        <div className="bg-zinc-900 border border-white/20 px-3 py-2 text-sm">
          <div className="text-gray-400">{monthYear}</div>
          <div className="text-white font-bold">{payload[0].value.toLocaleString()} jobs</div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      
      {/* MARKET PULSE - Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* 1. ACTIVE POSTINGS */}
        <div className="p-5 bg-white/5 border border-white/10">
          <div className="text-xs font-bold tracking-wider text-gray-500 mb-2">
            ACTIVE POSTINGS
          </div>
          <div className="text-3xl font-black">
            {totalJobs.toLocaleString()}
          </div>
          <div className="text-sm text-gray-500 mt-1">
            jobs analyzed
          </div>
        </div>
        
        {/* 2. POSTING GROWTH */}
        <div className="p-5 bg-white/5 border border-white/10">
          <div className="text-xs font-bold tracking-wider text-gray-500 mb-2">
            POSTING GROWTH
          </div>
          {marketTrend?.postings_growth_pct != null ? (
            <>
              <div className={`text-3xl font-black ${
                marketTrend.postings_growth_pct > 0 ? 'text-green-400' :
                marketTrend.postings_growth_pct < 0 ? 'text-red-400' :
                'text-gray-400'
              }`}>
                {marketTrend.postings_growth_pct > 0 ? '+' : ''}
                {marketTrend.postings_growth_pct}%
              </div>
              <div className="text-sm text-gray-500 mt-1">
                vs prior {marketTrend.window_days || 30} days
              </div>
              {marketTrend.new_companies_count > 0 && (
                <div className="text-xs text-gray-600 mt-1">
                  +{marketTrend.new_companies_count} new {marketTrend.new_companies_count === 1 ? 'company' : 'companies'} added
                </div>
              )}
            </>
          ) : (
            <>
              <div className="text-3xl font-black text-gray-600">—</div>
              <div className="text-sm text-gray-500 mt-1">
                Not enough historical data
              </div>
            </>
          )}
        </div>

        {/* 3. COMPANIES HIRING */}
        <div className="p-5 bg-white/5 border border-white/10">
          <div className="text-xs font-bold tracking-wider text-gray-500 mb-2">
            COMPANIES HIRING
          </div>
          <div className="text-3xl font-black">
            {companyCount.toLocaleString()}
          </div>
          <div className="text-sm text-gray-500 mt-1">
            active employers
          </div>
        </div>

        {/* 4. SKILLS TRACKED */}
        <div className="p-5 bg-white/5 border border-white/10">
          <div className="text-xs font-bold tracking-wider text-gray-500 mb-2">
            SKILLS TRACKED
          </div>
          <div className="text-3xl font-black">
            {skillBreadth}
          </div>
          <div className="text-sm text-gray-500 mt-1">
            {tableStakesCount} are must-haves
          </div>
        </div>
      </div>

      {/* 2x2 GRID: Trend + Salary | Companies + Skills */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* LEFT COLUMN */}
        <div className="space-y-6">
          
          {/* JOB POSTINGS TREND */}
          <div className="p-6 bg-white/5 border border-white/10">
            <div className="text-xs font-bold tracking-wider text-gray-500 mb-4">
              JOB POSTINGS TREND
            </div>
            
            {trendData.length > 0 ? (
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trendData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                    <XAxis 
                      dataKey="date" 
                      tickFormatter={(dateStr) => {
                        const date = new Date(dateStr);
                        return date.toLocaleDateString('en-US', { month: 'short' });
                      }}
                      stroke="#525252"
                      tick={{ fill: '#a3a3a3', fontSize: 11 }}
                      axisLine={{ stroke: '#404040' }}
                      tickLine={false}
                    />
                    <YAxis 
                      stroke="#525252"
                      tick={{ fill: '#737373', fontSize: 11 }}
                      axisLine={{ stroke: '#404040' }}
                      tickLine={false}
                      width={35}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar 
                      dataKey="count" 
                      fill="#ffffff"
                      radius={[2, 2, 0, 0]}
                      activeBar={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <div className="text-3xl mb-2">📊</div>
                  <div>Trend data coming soon</div>
                </div>
              </div>
            )}
          </div>

          {/* SALARY RANGE */}
          <div className="p-6 bg-white/5 border border-white/10">
            <div className="text-xs font-bold tracking-wider text-gray-500 mb-4">
              SALARY
            </div>
            
            {salaryInfo && salaryInfo.median ? (
              <>
                <div className="text-5xl font-black mb-2">
                  {formatSalary(salaryInfo.median)}
                </div>
                <div className="text-sm text-gray-500 mb-4">median</div>
                
                <div className="text-sm text-gray-400">
                  Range: {formatSalary(salaryInfo.min)} — {formatSalary(salaryInfo.max)}
                </div>
                
                <div className="text-xs text-gray-600 mt-2">
                  Based on {salaryInfo.jobs_with_salary?.toLocaleString()} jobs ({salaryInfo.salary_coverage_pct}%)
                </div>
              </>
            ) : (
              <div className="flex items-center gap-4 py-2">
                <div className="text-4xl">💰</div>
                <div>
                  <div className="font-bold mb-1">Limited Salary Data</div>
                  <div className="text-sm text-gray-500">Not enough data for this filter</div>
                </div>
              </div>
            )}
          </div>

          {/* WORK ARRANGEMENT */}
          <div className="p-6 bg-white/5 border border-white/10">
            <div className="text-xs font-bold tracking-wider text-gray-500 mb-4">
              WORK ARRANGEMENT
            </div>
            
            {(() => {
              const remoteCount = roleData?.remote_count || 0;
              const onsiteCount = roleData?.onsite_count || 0;
              const total = remoteCount + onsiteCount;
              const remotePercent = total > 0 ? Math.round((remoteCount / total) * 100) : 0;
              
              if (total === 0) {
                return (
                  <div className="text-center py-4">
                    <div className="text-2xl mb-2">🏢</div>
                    <div className="text-gray-500 text-sm">No location data available</div>
                  </div>
                );
              }
              
              return (
                <>
                  {/* Visual bar */}
                  <div className="flex h-3 rounded-full overflow-hidden mb-4">
                    <div 
                      className="bg-green-500" 
                      style={{ width: `${remotePercent}%` }}
                      title={`Remote: ${remotePercent}%`}
                    />
                    <div 
                      className="bg-white/30" 
                      style={{ width: `${100 - remotePercent}%` }}
                      title={`On-site: ${100 - remotePercent}%`}
                    />
                  </div>
                  
                  {/* Stats */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-green-500 rounded-sm" />
                        <span className="text-sm">Remote</span>
                      </div>
                      <span className="font-bold">{remoteCount.toLocaleString()} jobs ({remotePercent}%)</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-white/30 rounded-sm" />
                        <span className="text-sm">On-site / Hybrid</span>
                      </div>
                      <span className="font-bold">{onsiteCount.toLocaleString()} jobs ({100 - remotePercent}%)</span>
                    </div>
                  </div>
                </>
              );
            })()}
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div className="space-y-6">
          
          {/* TOP COMPANIES */}
          <div className="p-6 bg-white/5 border border-white/10">
            <div className="text-xs font-bold tracking-wider text-gray-500 mb-4">
              TOP COMPANIES
            </div>
            
            {topCompanies.length > 0 ? (
              <>
                <div className="space-y-2">
                  {topCompanies.slice(0, 5).map((company, idx) => (
                    <div 
                      key={company.id}
                      className="flex items-center justify-between py-2"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-600 w-4">{idx + 1}</span>
                        <span className="font-medium">{company.name}</span>
                      </div>
                      <span className="text-sm text-gray-400">
                        {company.job_count?.toLocaleString()} jobs
                      </span>
                    </div>
                  ))}
                </div>

                <button
                  onClick={() => setActiveTab('employers')}
                  className="mt-6 w-full px-4 py-3 bg-white/5 border border-white/20 hover:bg-white/10 transition-colors text-left flex items-center justify-between group"
                >
                  <div>
                    <div className="font-bold">View all {companyCount} employers</div>
                    <div className="text-sm text-gray-400">Compare openings and growth</div>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-500 group-hover:text-white transition-colors" />
                </button>
              </>
            ) : (
              <div className="text-gray-500 text-center py-6">No company data available</div>
            )}
          </div>

          {/* TOP SKILLS */}
          <div className="p-6 bg-white/5 border border-white/10">
            <div className="text-xs font-bold tracking-wider text-gray-500 mb-4">
              TOP SKILLS
            </div>
            
            {skills.length > 0 ? (
              <>
                <div className="space-y-2">
                  {skills.slice(0, 5).map((skill, idx) => (
                    <div key={skill.skill_id || idx} className="py-2">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-600 w-4">{idx + 1}</span>
                          <span className="font-medium">{skill.name}</span>
                        </div>
                        <span className="text-sm font-bold">{skill.demand}%</span>
                      </div>
                      <div className="ml-7 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-white rounded-full" 
                          style={{ width: `${skill.demand}%` }} 
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  onClick={() => setActiveTab('skills')}
                  className="mt-6 w-full px-4 py-3 bg-white/5 border border-white/20 hover:bg-white/10 transition-colors text-left flex items-center justify-between group"
                >
                  <div>
                    <div className="font-bold">Explore all {skillBreadth} skills</div>
                    <div className="text-sm text-gray-400">Filter, sort, and drill down</div>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-500 group-hover:text-white transition-colors" />
                </button>
              </>
            ) : (
              <div className="text-gray-500 text-center py-6">No skills data available</div>
            )}
          </div>
        </div>
      </div>
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
          <span className="text-gray-600">↕</span>
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
        <div className="text-sm text-gray-400">
          Showing <span className="text-white font-bold">{sortedCompanies.length}</span> employers
          {totalJobs > 0 && (
            <span className="text-gray-500"> • {totalJobs.toLocaleString()} total jobs</span>
          )}
        </div>
      </div>

      {/* Employers Table */}
      <div className="bg-white/5 border border-white/10 overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/10 text-xs font-bold text-gray-500 tracking-wider">
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
            <div className="px-6 py-12 text-center text-gray-500">
              No employers found matching your criteria.
            </div>
          ) : (
            sortedCompanies.map((company, idx) => (
              <div
                key={company.id}
                className="grid grid-cols-12 gap-4 px-6 py-4 hover:bg-white/5 transition-colors"
              >
                {/* Company Name */}
                <div className="col-span-4">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-600 w-6">{idx + 1}</span>
                    <span className="font-medium">{company.name}</span>
                  </div>
                </div>

                {/* Industry */}
                <div className="col-span-3">
                  {company.industry ? (
                    <span className="px-2 py-1 text-xs bg-white/10 border border-white/10 text-gray-300">
                      {company.industry}
                    </span>
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </div>

                {/* Job Count */}
                <div className="col-span-3">
                  <span className="font-bold">{company.job_count?.toLocaleString() || '—'}</span>
                </div>

                {/* Growth */}
                <div className="col-span-2">
                  {company.growth_pct != null ? (
                    <span className={`font-bold ${
                      company.growth_pct > 0 ? 'text-green-400' :
                      company.growth_pct < 0 ? 'text-red-400' :
                      'text-gray-400'
                    }`}>
                      {company.growth_pct > 0 ? '+' : ''}
                      {company.growth_pct}%
                    </span>
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer Note */}
      {sortedCompanies.some(c => c.growth_pct == null) && (
        <div className="text-xs text-gray-500 text-center">
          Growth rate compares current vs prior 30-day period. — indicates insufficient data.
        </div>
      )}
    </div>
  );
};

// ============================================
// SKILLS TAB (Explore Skills)
// ============================================
const SkillsTab = () => {
  const { roleData } = useApp();
  const [sortColumn, setSortColumn] = useState('demand');
  const [sortDirection, setSortDirection] = useState('desc');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [selectedSkill, setSelectedSkill] = useState(null);

  const skills = roleData?.skills || [];

  // Filter by category
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
          <span className="text-gray-600">↕</span>
        )}
      </span>
    </button>
  );

  const categories = [...new Set(skills.map(s => s.category).filter(Boolean))];

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="text-sm text-gray-400">
          Showing <span className="text-white font-bold">{sortedSkills.length}</span> skills
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
      <div className="bg-white/5 border border-white/10 overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/10 text-xs font-bold text-gray-500 tracking-wider">
          <div className="col-span-3">
            <SortHeader column="name" label="SKILL" />
          </div>

          <div className="col-span-2">
            <SortHeader column="category" label="CATEGORY" />
          </div>

          {/* add right padding here */}
          <div className="col-span-5 pr-10">
            <SortHeader column="demand" label="CURRENT DEMAND" />
          </div>

          <div className="col-span-2 pl-6 border-l border-white/10">
            <SortHeader column="growth" label="GROWTH (Δ)" />
          </div>
        </div>

        {/* Rows */}
        <div className="divide-y divide-white/5">
          {sortedSkills.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              No skills found matching your criteria.
            </div>
          ) : (
            sortedSkills.map((skill, idx) => (
              <button
                key={skill.skill_id || idx}
                onClick={() => setSelectedSkill(skill)}
                className="w-full grid grid-cols-12 gap-4 px-6 py-4 hover:bg-white/5 transition-colors text-left"
              >
                <div className="col-span-3 font-medium">{skill.name}</div>

                <div className="col-span-2">
                  <span className="px-2 py-1 text-xs font-bold bg-white/10 text-gray-200 border border-white/10">
                    {(skill.category || 'other').toUpperCase()}
                  </span>
                </div>

                {/* add right padding here too */}
                <div className="col-span-5 pr-10">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                      <div className="h-full bg-white" style={{ width: `${skill.demand}%` }} />
                    </div>
                    <span className="text-sm font-bold w-14 text-right">{skill.demand}%</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    {skill.job_count?.toLocaleString() || '—'} jobs
                  </div>
                </div>
                <div className="col-span-2 pl-6 border-l border-white/10">
                  {skill.growth_pct != null ? (
                    <span className={`text-sm font-bold ${
                      skill.growth_pct > 0 ? 'text-green-400' :
                      skill.growth_pct < 0 ? 'text-red-400' :
                      'text-gray-400'
                    }`}>
                      {skill.growth_pct > 0 ? '+' : ''}
                      {skill.growth_pct}%
                    </span>
                  ) : (
                    <span className="text-sm text-gray-600">—</span>
                  )}
                </div>
              </button>
            ))
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
      <div className="bg-zinc-900 border border-white/20 max-w-lg w-full max-h-[80vh] overflow-y-auto">
        <div className="p-6 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-2xl font-black">{skill.name}</h2>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <div className="p-6 space-y-6">
          {/* Demand */}
          <div>
            <div className="text-sm text-gray-500 mb-2">DEMAND FOR {selectedRole?.toUpperCase()}</div>
            <div className="flex items-center gap-4">
              <div className="text-5xl font-black">{skill.demand}%</div>
              <div className="text-gray-400">
                of jobs require this skill
              </div>
            </div>
          </div>

          {/* Category */}
          <div>
            <div className="text-sm text-gray-500 mb-2">CATEGORY</div>
            <span className="px-3 py-1 text-sm font-bold bg-white/10 text-gray-200 border border-white/10">
              {(skill.category || 'other').toUpperCase()}
            </span>
          </div>

          {/* Job Count */}
          <div>
            <div className="text-sm text-gray-500 mb-2">APPEARING IN</div>
            <div className="text-2xl font-bold">
              {skill.job_count?.toLocaleString() || '—'} jobs
            </div>
          </div>

          {/* Learning Resources */}
          <div className="pt-4 border-t border-white/10">
            <div className="text-sm text-gray-500 mb-3">LEARN THIS SKILL</div>
            <div className="space-y-2">
              <a 
                href={`https://www.coursera.org/search?query=${encodeURIComponent(skill.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full p-3 bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-left flex items-center justify-between"
              >
                <span>Search on Coursera</span>
                <ExternalLink className="w-4 h-4 text-gray-500" />
              </a>
              <a 
                href={`https://www.udemy.com/courses/search/?q=${encodeURIComponent(skill.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full p-3 bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-left flex items-center justify-between"
              >
                <span>Search on Udemy</span>
                <ExternalLink className="w-4 h-4 text-gray-500" />
              </a>
              <a 
                href={`https://www.youtube.com/results?search_query=${encodeURIComponent(skill.name + ' tutorial')}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full p-3 bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-left flex items-center justify-between"
              >
                <span>Search on YouTube</span>
                <ExternalLink className="w-4 h-4 text-gray-500" />
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
      <div className="text-gray-400">
        Based on skill overlap with <span className="text-white font-bold">{selectedRole}</span>, 
        here are roles you might also consider.
      </div>

      {alternativeRoles.length === 0 ? (
        <div className="space-y-6">
          <div className="p-12 bg-white/5 border border-white/10 text-center">
            <div className="text-4xl mb-4">🔍</div>
            <div className="text-xl font-bold mb-2">No alternative roles found</div>
            <div className="text-gray-400">
              We're still building our role comparison data. Check back soon!
            </div>
          </div>

          {/* Preview/Example Section */}
          <div className="space-y-4">
            <div className="text-sm text-gray-500 mb-4">
              Example of what this will look like:
            </div>
            {[
              { 
                title: 'Technical Product Manager', 
                skill_overlap: 78, 
                job_count: 234,
                salary_min: 120000,
                salary_max: 180000,
                salary_currency: 'USD',
                shared_skills: ['Product Strategy', 'Roadmapping', 'Stakeholder Management', 'Agile'],
                new_skills: ['SQL', 'API Design', 'System Architecture']
              },
              { 
                title: 'Product Designer', 
                skill_overlap: 62, 
                job_count: 189,
                salary_min: 95000,
                salary_max: 155000,
                salary_currency: 'USD',
                shared_skills: ['User Research', 'Wireframing', 'Prototyping'],
                new_skills: ['Figma', 'Visual Design', 'Design Systems']
              },
              { 
                title: 'Program Manager', 
                skill_overlap: 71, 
                job_count: 156,
                salary_min: 110000,
                salary_max: 170000,
                salary_currency: 'USD',
                shared_skills: ['Stakeholder Management', 'Roadmapping', 'Cross-functional Leadership'],
                new_skills: ['Risk Management', 'Resource Planning', 'Budget Management']
              },
            ].map((role, idx) => (
              <div 
                key={idx}
                className="p-6 bg-white/5 border border-white/10 opacity-60"
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-xl font-black mb-1">{role.title}</h3>
                    <div className="text-sm text-gray-400">
                      {role.job_count?.toLocaleString() || '—'} open positions
                    </div>
                    {/* Salary Range */}
                    {(role.salary_min || role.salary_max) && (
                      <div className="text-sm text-green-400 mt-1 flex items-center gap-1">
                        <span>💰</span>
                        <span>{formatSalaryRange(role.salary_min, role.salary_max, role.salary_currency)}</span>
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className={`text-3xl font-black ${
                      role.skill_overlap >= 70 ? 'text-green-500' :
                      role.skill_overlap >= 50 ? 'text-yellow-500' :
                      'text-orange-500'
                    }`}>
                      {role.skill_overlap}%
                    </div>
                    <div className="text-xs text-gray-500">SKILL OVERLAP</div>
                  </div>
                </div>

                <div className="mb-4">
                  <div className="text-xs text-gray-500 mb-2">SHARED SKILLS</div>
                  <div className="flex flex-wrap gap-2">
                    {role.shared_skills.map((skill, skillIdx) => (
                      <span 
                        key={skillIdx}
                        className="px-2 py-1 bg-green-500/20 border border-green-500/30 text-xs text-green-400"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mb-4">
                  <div className="text-xs text-gray-500 mb-2">SKILLS GAP</div>
                  <div className="flex flex-wrap gap-2">
                    {role.new_skills.map((skill, skillIdx) => (
                      <span 
                        key={skillIdx}
                        className="px-2 py-1 bg-orange-500/20 border border-orange-500/30 text-xs text-orange-400"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="text-xs text-gray-500 italic">
                  (Preview - data coming soon)
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {alternativeRoles.map((role, idx) => (
            <div 
              key={idx}
              className="p-6 bg-white/5 border border-white/10 hover:bg-white/[0.07] transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-black mb-1">{role.title}</h3>
                  <div className="text-sm text-gray-400 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>{role.job_count?.toLocaleString() || '—'} open positions</span>
                    {role.posting_growth_pct != null && (
                      <span className={`font-medium ${
                        role.posting_growth_pct > 0 ? 'text-green-400' :
                        role.posting_growth_pct < 0 ? 'text-red-400' :
                        'text-gray-400'
                      }`}>
                        ({role.posting_growth_pct > 0 ? '+' : ''}{role.posting_growth_pct}% growth)
                      </span>
                    )}
                  </div>
                  
                  {/* Salary Range */}
                  {(role.salary_min || role.salary_max) && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-green-400 font-bold">
                        {formatSalaryRange(role.salary_min, role.salary_max, role.salary_currency)}
                      </span>
                      {role.salary_currency && role.salary_currency !== 'USD' && (
                        <span className="text-xs text-gray-500 bg-white/10 px-1.5 py-0.5">
                          {role.salary_currency}
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <div className={`text-3xl font-black ${
                    role.skill_overlap >= 70 ? 'text-green-500' :
                    role.skill_overlap >= 50 ? 'text-yellow-500' :
                    'text-orange-500'
                  }`}>
                    {role.skill_overlap}%
                  </div>
                  <div className="text-xs text-gray-500">SKILL OVERLAP</div>
                </div>
              </div>

              {/* Shared Skills */}
              {role.shared_skills && role.shared_skills.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs text-gray-500 mb-2">SHARED SKILLS</div>
                  <div className="flex flex-wrap gap-2">
                    {role.shared_skills.slice(0, 6).map((skill, skillIdx) => (
                      <span 
                        key={skillIdx}
                        className="px-2 py-1 bg-green-500/20 border border-green-500/30 text-xs text-green-400"
                      >
                        {skill}
                      </span>
                    ))}
                    {role.shared_skills.length > 6 && (
                      <span className="px-2 py-1 text-xs text-gray-500">
                        +{role.shared_skills.length - 6} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Skills You'd Need to Learn */}
              {role.new_skills && role.new_skills.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs text-gray-500 mb-2">SKILLS GAP</div>
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
                      <span className="px-2 py-1 text-xs text-gray-500">
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
                className={`px-4 py-2 font-bold text-sm flex items-center gap-2 transition-colors ${
                  loading 
                    ? 'bg-white/20 text-gray-400 cursor-not-allowed' 
                    : 'bg-white text-black hover:bg-gray-200'
                }`}
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin"></div>
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
const LoadingScreen = () => (
  <div className="min-h-screen bg-black text-white flex items-center justify-center">
    <div className="text-center">
      <div className="mb-8 flex justify-center gap-2">
        <div className="w-3 h-3 bg-white animate-pulse" style={{ animationDelay: '0ms' }}></div>
        <div className="w-3 h-3 bg-white animate-pulse" style={{ animationDelay: '150ms' }}></div>
        <div className="w-3 h-3 bg-white animate-pulse" style={{ animationDelay: '300ms' }}></div>
      </div>
      <div className="text-3xl font-black mb-4">ANALYZING</div>
      <div className="text-gray-500">Gathering market intelligence...</div>
    </div>
  </div>
);

// ============================================
// INITIAL LOADING SCREEN (for app startup)
// ============================================
const InitialLoadingScreen = () => (
  <div className="min-h-screen bg-black text-white flex items-center justify-center">
    <div className="text-center">
      <div className="mb-8 flex justify-center gap-2">
        <div className="w-3 h-3 bg-white animate-pulse" style={{ animationDelay: '0ms' }}></div>
        <div className="w-3 h-3 bg-white animate-pulse" style={{ animationDelay: '150ms' }}></div>
        <div className="w-3 h-3 bg-white animate-pulse" style={{ animationDelay: '300ms' }}></div>
      </div>
      <div className="text-lg font-bold tracking-widest">WhatsInDemand</div>
    </div>
  </div>
);

// ============================================
// ACCOUNT SCREEN
// ============================================
const AccountScreen = () => {
  const { 
    user, 
    setCurrentScreen, 
    handleLogout,
    roleData 
  } = useApp();

  // Redirect if not logged in
  useEffect(() => {
    if (!user) {
      setCurrentScreen('login');
    }
  }, [user, setCurrentScreen]);

  if (!user) {
    return <LoadingScreen />;
  }

  return (
    <div className="min-h-screen bg-black text-white flex">
      <DashboardSidebar />

      <div className="flex-1 ml-64">
        <div className="max-w-3xl mx-auto px-8 pt-8 pb-24">
          
          {/* Header */}
          <div className="mb-8">
            <button
              onClick={() => roleData ? setCurrentScreen('dashboard') : setCurrentScreen('role-selection')}
              className="text-sm text-gray-400 hover:text-white transition-colors mb-4 flex items-center gap-2"
            >
              ← Back
            </button>
            <h1 className="text-5xl font-black tracking-tight">
              ACCOUNT
            </h1>
          </div>

          {/* Profile Section */}
          <div className="space-y-6">
            
            {/* User Info Card */}
            <div className="p-6 bg-white/5 border border-white/10">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-16 h-16 bg-white/10 rounded-full flex items-center justify-center">
                  <span className="text-2xl font-bold">
                    {user.full_name?.charAt(0) || user.email?.charAt(0) || 'U'}
                  </span>
                </div>
                <div>
                  <h2 className="text-xl font-bold">{user.full_name || 'User'}</h2>
                  <p className="text-gray-400">{user.email}</p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between py-3 border-b border-white/10">
                  <span className="text-gray-400">Full Name</span>
                  <span className="font-medium">{user.full_name || '—'}</span>
                </div>
                <div className="flex justify-between py-3 border-b border-white/10">
                  <span className="text-gray-400">Email</span>
                  <span className="font-medium">{user.email}</span>
                </div>
                <div className="flex justify-between py-3 border-b border-white/10">
                  <span className="text-gray-400">Account Type</span>
                  <span className={`font-medium ${user.has_pro_access ? 'text-green-400' : ''}`}>
                    {user.has_pro_access ? 'Pro' : 'Free'}
                  </span>
                </div>
                <div className="flex justify-between py-3">
                  <span className="text-gray-400">Member Since</span>
                  <span className="font-medium">
                    {user.created_at 
                      ? new Date(user.created_at).toLocaleDateString('en-US', { 
                          month: 'long', 
                          year: 'numeric' 
                        })
                      : '—'
                    }
                  </span>
                </div>
              </div>
            </div>

            {/* Pro Upgrade Card (only show for free users) */}
            {!user.has_pro_access && (
              <div className="p-6 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-bold mb-2 flex items-center gap-2">
                      <Zap className="w-5 h-5 text-yellow-500" />
                      Upgrade to Pro
                    </h3>
                    <p className="text-gray-400 text-sm mb-4">
                      Get access to personalized job matching, skill gap analysis, and more.
                    </p>
                  </div>
                </div>
                <button
                  className="px-6 py-3 bg-white text-black font-bold hover:bg-gray-200 transition-colors"
                  onClick={() => alert('Pro upgrade coming soon!')}
                >
                  COMING SOON
                </button>
              </div>
            )}

            {/* Actions */}
            <div className="space-y-3">
              <button
                onClick={() => setCurrentScreen('role-selection')}
                className="w-full p-4 bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-left flex items-center justify-between"
              >
                <div>
                  <div className="font-bold">Explore a New Role</div>
                  <div className="text-sm text-gray-400">Discover skills and trends for any role</div>
                </div>
                <ArrowRight className="w-5 h-5 text-gray-500" />
              </button>

              <button
                onClick={handleLogout}
                className="w-full p-4 border border-white/20 hover:bg-white/5 transition-colors text-left text-gray-400 hover:text-white"
              >
                Sign Out
              </button>
            </div>

          </div>
        </div>

        <Footer />
      </div>
    </div>
  );
};

// ============================================
// MAIN APP ROUTER
// ============================================
const AppRouter = () => {
  const { currentScreen, loading, initialLoading } = useApp();

  // Scroll to top on screen change
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [currentScreen]);
  
  // Show initial loading screen while checking auth
  if (initialLoading) {
    return <InitialLoadingScreen />;
  }

  switch (currentScreen) {
    case 'landing':
      return <LandingScreen />;
    case 'login':
      return <LoginScreen />;
    case 'signup':
      return <SignupScreen />;
    case 'role-selection':
      return <RoleSelectionScreen />;
    case 'dashboard':
      return <DashboardScreen />;
    case 'account':
      return <AccountScreen />;
    default:
      return <LandingScreen />;
  }
};

// ============================================
// MAIN APP COMPONENT
// ============================================
const WhatsInDemand = () => {
  return (
    <AppProvider>
      <AppRouter />
    </AppProvider>
  );
};

export default WhatsInDemand;