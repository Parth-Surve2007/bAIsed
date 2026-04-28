// Client-side Firebase auth scaffold.
// Full implementation is intentionally deferred until the dedicated auth pass.

function signInWithEmail(_email, _password) {
  return Promise.reject(new Error("Firebase email sign-in is not wired yet."));
}

function signUpWithEmail(_fullName, _email, _password, _confirmPassword) {
  return Promise.reject(new Error("Firebase sign-up is not wired yet."));
}

function signInWithGoogle() {
  return Promise.reject(new Error("Google OAuth is not wired yet."));
}

function signOut() {
  return Promise.reject(new Error("Sign-out is not wired yet."));
}

function getIdToken() {
  return Promise.reject(new Error("ID token retrieval is not wired yet."));
}

function handlePendingAuthRedirect() {
  // Placeholder for future onAuthStateChanged redirect behavior.
}

window.baisedAuth = {
  signInWithEmail,
  signUpWithEmail,
  signInWithGoogle,
  signOut,
  getIdToken,
  handlePendingAuthRedirect,
};
