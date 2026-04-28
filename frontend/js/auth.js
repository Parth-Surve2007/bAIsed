(() => {
  const EMAIL_KEY = "baised_user_email";
  const TOKEN_KEY = "baised_demo_token";
  const AUTH_PROVIDER_KEY = "baised_auth_provider";
  const FORCE_LOGOUT_KEY = "baised_force_logged_out";
  const REDIRECT_FALLBACK = "/workbench";

  function getAuth() {
    const auth = window.baisedFirebase && window.baisedFirebase.auth;
    if (!auth) {
      throw new Error("Firebase Auth SDK failed to initialize.");
    }
    return auth;
  }

  function getRedirectTarget() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("logged_out") === "1") {
      return "/login";
    }
    return params.get("redirect") || REDIRECT_FALLBACK;
  }

  function setStatus(id, message) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = message;
    }
  }

  function bindPasswordVisibilityToggles() {
    document.querySelectorAll("[data-password-toggle]").forEach((button) => {
      if (button.dataset.toggleBound === "true") {
        return;
      }
      button.dataset.toggleBound = "true";

      const selector = button.getAttribute("data-password-toggle");
      if (!selector) {
        return;
      }

      const input = document.querySelector(selector);
      const icon = button.querySelector(".material-symbols-outlined");
      if (!input) {
        return;
      }

      button.addEventListener("click", () => {
        const showing = input.getAttribute("type") === "text";
        input.setAttribute("type", showing ? "password" : "text");
        if (icon) {
          icon.textContent = showing ? "visibility" : "visibility_off";
        }
        button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      });
    });
  }

  function dispatchAuthChanged(detail) {
    document.dispatchEvent(new CustomEvent("baised:auth-changed", { detail }));
  }

  async function persistAuthSession(user, provider = "firebase") {
    if (!user) {
      clearStoredSession();
      return null;
    }

    const token = await user.getIdToken();
    const email = user.email || "";
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(EMAIL_KEY, email);
    localStorage.setItem(AUTH_PROVIDER_KEY, provider);
    localStorage.removeItem(FORCE_LOGOUT_KEY);
    dispatchAuthChanged({ email, provider, signedIn: true });
    return { token, email };
  }

  function clearStoredSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(AUTH_PROVIDER_KEY);
    dispatchAuthChanged({ email: null, provider: null, signedIn: false });
  }

  function validateEmailPassword(email, password) {
    if (!String(email || "").trim()) {
      throw new Error("Enter your email address.");
    }
    if (!String(password || "").trim()) {
      throw new Error("Enter your password.");
    }
  }

  async function signInWithEmail(email, password) {
    validateEmailPassword(email, password);
    const auth = getAuth();
    const credential = await auth.signInWithEmailAndPassword(email.trim(), password);
    await persistAuthSession(credential.user, "firebase-password");
    return credential.user;
  }

  async function signUpWithEmail(fullName, email, password, confirmPassword) {
    const trimmedName = String(fullName || "").trim();
    validateEmailPassword(email, password);
    if (!trimmedName) {
      throw new Error("Enter your full name.");
    }
    if (password.length < 6) {
      throw new Error("Password must be at least 6 characters.");
    }
    if (password !== confirmPassword) {
      throw new Error("Passwords do not match.");
    }

    const auth = getAuth();
    const credential = await auth.createUserWithEmailAndPassword(email.trim(), password);
    if (trimmedName) {
      await credential.user.updateProfile({ displayName: trimmedName });
    }
    await persistAuthSession(credential.user, "firebase-password");
    return credential.user;
  }

  async function signInWithGoogle() {
    const auth = getAuth();
    const provider = new window.firebase.auth.GoogleAuthProvider();
    provider.setCustomParameters({ prompt: "select_account" });
    const credential = await auth.signInWithPopup(provider);
    await persistAuthSession(credential.user, "firebase-google");
    return credential.user;
  }

  async function signOut() {
    const auth = getAuth();
    try {
      await auth.signOut();
    } finally {
      clearStoredSession();
    }
  }

  async function getIdToken() {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) {
      throw new Error("No signed-in user.");
    }
    const token = await user.getIdToken(true);
    localStorage.setItem(TOKEN_KEY, token);
    return token;
  }

  async function handlePendingAuthRedirect() {
    const page = document.body.dataset.page || "";
    const auth = getAuth();
    const params = new URLSearchParams(window.location.search);
    const isLoggedOutLanding = params.get("logged_out") === "1";
    const forceLoggedOut = localStorage.getItem(FORCE_LOGOUT_KEY) === "1";

    auth.onIdTokenChanged(async (user) => {
      if (!user) {
        clearStoredSession();
        return;
      }

      if (forceLoggedOut || isLoggedOutLanding) {
        try {
          await auth.signOut();
        } finally {
          clearStoredSession();
        }
        return;
      }

      try {
        await persistAuthSession(user, "firebase-session");
        if ((page === "login" || page === "signup") && !isLoggedOutLanding) {
          window.location.replace(getRedirectTarget());
        }
      } catch (_error) {
        clearStoredSession();
      }
    });

    if (isLoggedOutLanding) {
      return;
    }

    const currentUser = auth.currentUser;
    if (!currentUser) {
      return;
    }

    if (forceLoggedOut) {
      try {
        await auth.signOut();
      } finally {
        clearStoredSession();
      }
      return;
    }

    await persistAuthSession(currentUser, "firebase-session");
    if (page === "login" || page === "signup") {
      window.location.replace(getRedirectTarget());
    }
  }

  function bindLoginPage() {
    const form = document.getElementById("login-form");
    if (!form) {
      return;
    }

    const googleButton = document.getElementById("google-signin-btn");
    const submitButton = form.querySelector('button[type="submit"]');

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const email = document.getElementById("email")?.value || "";
      const password = document.getElementById("password")?.value || "";

      try {
        if (submitButton) {
          submitButton.disabled = true;
        }
        setStatus("login-status", "Signing you in...");
        await signInWithEmail(email, password);
        setStatus("login-status", "Signed in. Redirecting...");
        window.location.replace(getRedirectTarget());
      } catch (error) {
        setStatus("login-status", error.message || "Unable to sign in.");
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
        }
      }
    });

    if (googleButton) {
      googleButton.addEventListener("click", async () => {
        try {
          setStatus("login-status", "Opening Google sign-in...");
          await signInWithGoogle();
          setStatus("login-status", "Signed in with Google. Redirecting...");
          window.location.replace(getRedirectTarget());
        } catch (error) {
          setStatus("login-status", error.message || "Google sign-in failed.");
        }
      });
    }

  }

  function bindSignupPage() {
    const form = document.getElementById("signup-form");
    if (!form) {
      return;
    }

    const googleButton = document.getElementById("google-signup-btn");
    const submitButton = form.querySelector('button[type="submit"]');
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = document.getElementById("signup-name")?.value || "";
      const email = document.getElementById("signup-email")?.value || "";
      const password = document.getElementById("signup-password")?.value || "";
      const confirmPassword = document.getElementById("signup-confirm-password")?.value || "";

      try {
        if (submitButton) {
          submitButton.disabled = true;
        }
        setStatus("signup-status", "Creating your account...");
        await signUpWithEmail(name, email, password, confirmPassword);
        setStatus("signup-status", "Account created. Redirecting...");
        window.location.replace(getRedirectTarget());
      } catch (error) {
        setStatus("signup-status", error.message || "Unable to create your account.");
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
        }
      }
    });

    if (googleButton) {
      googleButton.addEventListener("click", async () => {
        try {
          setStatus("signup-status", "Opening Google sign-up...");
          await signInWithGoogle();
          setStatus("signup-status", "Signed in with Google. Redirecting...");
          window.location.replace(getRedirectTarget());
        } catch (error) {
          setStatus("signup-status", error.message || "Google sign-up failed.");
        }
      });
    }
  }

  function bindDashboardPage() {
    const signOutButton = document.getElementById("dashboard-signout");
    const emailTarget = document.getElementById("dashboard-user-email");
    const greetingTarget = document.getElementById("dashboard-greeting");
    const email = localStorage.getItem(EMAIL_KEY) || "Signed-in user";

    if (emailTarget) {
      emailTarget.textContent = email;
    }
    if (greetingTarget) {
      greetingTarget.textContent = `Welcome back, ${email}.`;
    }

    if (!signOutButton) {
      return;
    }

    signOutButton.addEventListener("click", async () => {
      try {
        signOutButton.disabled = true;
        await signOut();
        window.location.replace("/login");
      } catch (_error) {
        signOutButton.disabled = false;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      await handlePendingAuthRedirect();
    } catch (error) {
      const page = document.body.dataset.page || "";
      if (page === "login") {
        setStatus("login-status", error.message || "Firebase auth failed to initialize.");
      }
      if (page === "signup") {
        setStatus("signup-status", error.message || "Firebase auth failed to initialize.");
      }
    }

    bindLoginPage();
    bindSignupPage();
    bindDashboardPage();
    bindPasswordVisibilityToggles();
  });

  window.baisedAuth = {
    signInWithEmail,
    signUpWithEmail,
    signInWithGoogle,
    signOut,
    getIdToken,
    handlePendingAuthRedirect,
  };
})();
