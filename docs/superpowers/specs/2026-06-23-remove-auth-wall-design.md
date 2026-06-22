# Remove Auth Wall — Design Spec
**Date:** 2026-06-23  
**Status:** Approved

## Problem

Anonymous users hit a signup wall before seeing any data. The current flow is:

```
Landing → Role Selection → [AUTH GATE] → Signup → Skills Input → Dashboard
```

Users invest effort picking a role and seniority, then must create an account before seeing a single data point. For a data/intelligence product, value must be demonstrated before it is promised.

## Goal

Let anonymous users reach the dashboard immediately. Gate only the personalization layer (skill gap analysis), which is the natural account hook.

## New Flow

**Anonymous:**
```
Landing → Role Selection → Dashboard (market data)
                                 ↓ (when they want to personalize)
                           Signup → Skills Input → Dashboard (personal gap)
```

**Authenticated (unchanged):**
```
Landing → Role Selection → Skills Input → Dashboard (personal gap)
```

## Changes

### 1. Remove auth gate in `RoleSelectionScreen.handleExplore`

Remove the `if (!user)` check that redirects to signup. Always call `exploreRole()`.

**Before:**
```js
const handleExplore = async () => {
  if (!user) {
    setCurrentScreen('signup');
  } else {
    await exploreRole();
  }
};
```

**After:**
```js
const handleExplore = async () => {
  await exploreRole();
};
```

### 2. Conditional routing in `exploreRole()` (AppProvider)

After fetching data, route to dashboard (not skills-input) for anonymous users.

```js
// After data fetch succeeds:
setCurrentScreen(user ? 'skills-input' : 'dashboard');
```

Session saving is already guarded by `if (user)` — no change needed there.

### 3. Same conditional in `switchToRole()` (AppProvider)

`switchToRole` (used by the Alternative Roles tab) has the same route-to-skills-input pattern. Apply identical conditional:

```js
setCurrentScreen(user ? 'skills-input' : 'dashboard');
```

### 4. Action strip sign-up CTA (OverviewTab)

The action strip currently has two states: with-skills (personal gap) and without-skills (generic leverage skill). Add a third state for anonymous users.

**Condition:** `!user && !hasUserSkills`  
**Copy:** "Sign up to add your skills and see your personal gap — free, takes 30 seconds →"  
**Style:** Same amber `bg-accent-warn/10` panel, `Clock` icon, CTA is a button that routes to `/signup`.

### 5. "EDIT MY SKILLS" button — route to signup for anonymous users

In `DashboardScreen` header (desktop) and `MobileHeader` menu:

```js
onClick={() => setCurrentScreen(user ? 'skills-input' : 'signup')}
```

Role, seniority, location, and roleData are already in state when the user arrives at signup. After account creation, `handleSignup → exploreRole()` routes them to skills-input with full context preserved.

## Edge Cases

| Scenario | Behaviour |
|---|---|
| Anonymous deep-link to `/dashboard` (no roleData) | Existing guard redirects to landing — no change |
| Anonymous deep-link to `/skills-input` | Existing guard redirects to role-selection — no change |
| Anonymous user signs up from action strip CTA | `handleSignup → exploreRole()` → skills-input → dashboard with personal gap |
| Returning authenticated user | Unchanged — goes through skills-input as before |
| `switchToRole` from Paths tab (anonymous) | Routes to dashboard, not skills-input |

## What Does Not Change

- NavBar already shows `SIGN IN` for anonymous users — no change needed
- Sidebar sign-out button is already guarded by `{user && ...}`
- Email verification banner is already guarded by `user && user.email_verified === false`
- Session persistence to localStorage still runs for anonymous users — state is preserved across sign-up

## Out of Scope

- Inline sign-up modal on the dashboard (can be added later if conversion data warrants it)
- Anonymous skill selection in skills-input (reduces sign-up urgency — deferred)
- Persistent "sign up" banner (not needed given contextual prompts)
