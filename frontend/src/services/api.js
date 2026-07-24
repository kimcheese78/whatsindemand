// services/api.js

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

class API {
  constructor() {
    this.baseURL = API_BASE_URL;
    this.token = localStorage.getItem('authToken');
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('authToken', token);
    } else {
      localStorage.removeItem('authToken');
    }
  }

  getHeaders(includeAuth = true) {
    const headers = {
      'Content-Type': 'application/json',
    };

    const token = this.token || localStorage.getItem('authToken');
    if (includeAuth && token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const timeoutMs = options.timeout ?? 15000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    // Forward external cancellation signal (e.g. AbortController from caller)
    if (options.signal) {
      options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }

    const config = {
      ...options,
      signal: controller.signal,
      headers: {
        ...this.getHeaders(options.auth !== false),
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);
      
      // Handle non-JSON responses
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        return { success: true };
      }
      
      const data = await response.json();

      // For 404s on role insights, return the data instead of throwing
      if (response.status === 404 && data.total_jobs_analyzed === 0) {
        return { ...data, success: false };
      }

      if (!response.ok) {
        throw new Error(data.error || data.message || 'Request failed');
      }

      return data;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out. Please check your connection and try again.');
      }
      console.error('API Error:', error);
      throw error;
    }
  }

  // ============================================
  // AUTH ENDPOINTS
  // ============================================

  async googleAuth(credential) {
    const data = await this.request('/api/auth/google', {
        method: 'POST',
        body: JSON.stringify({ credential }),
        auth: false,
    });
    if (data.token) this.setToken(data.token);
    return data;
}

  async signup(email, password, fullName, targetRole, seniorityLevel, location) {
    const data = await this.request('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        full_name: fullName,
        target_role: targetRole,
        seniority_level: seniorityLevel,
        location,
      }),
      auth: false,
    });

    if (data.token) {
      this.setToken(data.token);
    }

    return data;
  }

  async login(email, password) {
    const data = await this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      auth: false,
    });

    if (data.token) {
      this.setToken(data.token);
    }

    return data;
  }

  async getCurrentUser() {
    return this.request('/api/auth/me');
  }

  logout() {
    this.setToken(null);
  }

  // ============================================
  // ACCOUNT SAFETY
  // ============================================

  async forgotPassword(email) {
    return this.request('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
      auth: false,
    });
  }

  async resetPassword(token, newPassword) {
    const data = await this.request('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
      auth: false,
    });
    if (data.token) this.setToken(data.token);
    return data;
  }

  async changePassword(currentPassword, newPassword) {
    return this.request('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
  }

  async updateProfile({ full_name }) {
    return this.request('/api/auth/me', {
      method: 'PATCH',
      body: JSON.stringify({ full_name }),
    });
  }

  async requestEmailChange(newEmail, currentPassword) {
    return this.request('/api/auth/change-email', {
      method: 'POST',
      body: JSON.stringify({
        new_email: newEmail,
        current_password: currentPassword,
      }),
    });
  }

  async verifyEmail(token) {
    const data = await this.request('/api/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
      auth: false,
    });
    if (data.token) this.setToken(data.token);
    return data;
  }

  async resendVerification() {
    return this.request('/api/auth/resend-verification', {
      method: 'POST',
    });
  }

  async deleteAccount({ password, confirm }) {
    const body = {};
    if (password) body.password = password;
    if (confirm) body.confirm = confirm;
    return this.request('/api/auth/delete-account', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async exportData() {
    const url = `${this.baseURL}/api/auth/export-data`;
    const token = this.token || localStorage.getItem('authToken');
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      let message = 'Export failed';
      try { const j = await response.json(); message = j.error || message; } catch (e) {}
      throw new Error(message);
    }
    const blob = await response.blob();
    const filename = (response.headers.get('content-disposition') || '')
      .match(/filename="?([^"]+)"?/)?.[1] || 'whatsindemand-export.json';
    return { blob, filename };
  }

  // ============================================
  // SESSION PERSISTENCE
  // ============================================

  async saveSession(targetRole, seniorityLevel, location, analysisData = null) {
    return this.request('/api/session/save', {
      method: 'POST',
      body: JSON.stringify({
        target_role: targetRole,
        seniority_level: seniorityLevel,
        location: location,
        analysis: analysisData,
      }),
    });
  }

  async getLastSession() {
    return this.request('/api/session/last');
  }

  async clearSession() {
    return this.request('/api/session/clear', {
      method: 'POST',
    });
  }

  // ============================================
  // ROLE INTELLIGENCE ENDPOINTS
  // ============================================

  async getRoleInsights(role, seniority, location, industry = null, companyId = null, userSkills = null, signal = null) {
    const params = {
      role,
      seniority,
      location,
    };

    if (industry) params.industry = industry;
    if (companyId) params.company_id = companyId;
    if (userSkills && userSkills.length > 0) params.user_skills = userSkills.map(s => s.skill_id);

    return this.request('/api/roles/insights', {
      method: 'POST',
      body: JSON.stringify(params),
      auth: false,
      ...(signal && { signal }),
    });
  }

  async getAlternativeRoles(role, seniority = null) {
    return this.request('/api/roles/alternatives', {
      method: 'POST',
      body: JSON.stringify({ role, seniority }),
      auth: false,
    });
  }

  async getRoleDetails(roleId) {
    return this.request(`/api/roles/${roleId}`, {
      auth: false,
    });
  }

  // ============================================
  // LOCATIONS ENDPOINTS
  // ============================================

  async getLocations() {
    return this.request('/api/locations', {
      auth: false,
    });
  }

  // ============================================
  // SKILLS ENDPOINTS
  // ============================================

  async getSkillDetails(skillId, role = null) {
    const params = new URLSearchParams();
    if (role) params.append('role', role);
    
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/api/skills/${skillId}${query}`, {
      auth: false,
    });
  }

  async getAvailableSkills() {
    return this.request('/api/skills', {
      auth: false,
    });
  }

  async getCoOccurringSkills(skillId, roleId = null) {
    const query = roleId ? `?role_id=${roleId}` : '';
    return this.request(`/api/skills/${skillId}/co-occurring${query}`, {
      auth: false,
    });
  }

  async extractSkillsFromText(text) {
    return this.request('/api/skills/extract', {
      method: 'POST',
      body: JSON.stringify({ text, document_type: 'resume' }),
      auth: false,
    });
  }

  async extractSkillsFromFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    const url = `${this.baseURL}/api/skills/extract`;
    const response = await fetch(url, { method: 'POST', body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Extraction failed');
    return data;
  }

  // ============================================
  // MATCHED JOBS ENDPOINTS (auth required)
  // ============================================

  async getMatchedJobs() {
    return this.request('/api/matched-jobs');
  }

  async getMatchedJobsSummary() {
    return this.request('/api/matched-jobs/summary');
  }

  async getPositionScore() {
    return this.request('/api/position-score');
  }

  async syncUserSkills(skillIds) {
    return this.request('/api/skills/sync', {
      method: 'POST',
      body: JSON.stringify({ skill_ids: skillIds }),
    });
  }

  async setSkillStatus(skillId, status) {
    return this.request(`/api/learning/skills/${skillId}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    });
  }

  async getLearning() {
    return this.request('/api/learning');
  }

  // ============================================
  // COMPANIES ENDPOINTS
  // ============================================

  async getCompanies(minJobs = 1, industry = null) {
    const params = new URLSearchParams();
    params.append('min_jobs', minJobs);
    if (industry) params.append('industry', industry);
    
    return this.request(`/api/companies?${params.toString()}`, {
      auth: false,
    });
  }

  async getIndustries() {
    return this.request('/api/companies/industries', {
      auth: false,
    });
  }

  async getCompanyDetails(companyId) {
    return this.request(`/api/companies/${companyId}`, {
      auth: false,
    });
  }

  async getCompanySkills(companyId, role = null) {
    const params = new URLSearchParams();
    if (role) params.append('role', role);
    
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/api/companies/${companyId}/skills${query}`, {
      auth: false,
    });
  }

  // ============================================
  // JOBS ENDPOINTS
  // ============================================

  async getJobStats() {
    return this.request('/api/jobs/stats', {
      auth: false,
    });
  }

  async searchJobs(query, filters = {}) {
    return this.request('/api/jobs/search', {
      method: 'POST',
      body: JSON.stringify({ query, ...filters }),
      auth: false,
    });
  }

  // ============================================
  // SKILL GAP ENDPOINTS (existing)
  // ============================================

  async getAvailableRoles(minJobs = 3) {
    return this.request(`/api/skill-gap/roles?min_jobs=${minJobs}`, {
      auth: false,
    });
  }

  async getRoleCard(roleSlug, seniority = '', location = '') {
    const params = new URLSearchParams();
    if (seniority && seniority !== 'all') params.set('seniority', seniority);
    if (location && location !== 'all') params.set('location', location);
    const qs = params.toString() ? `?${params}` : '';
    return this.request(`/api/roles/card/${roleSlug}${qs}`, { auth: false });
  }
}

const api = new API();
export default api;