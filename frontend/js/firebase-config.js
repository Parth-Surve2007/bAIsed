// Firebase client bootstrap scaffold.
// Load the Firebase compat SDK via CDN before this file when implementation begins.
// The config values can be injected by Flask later or replaced during deployment.

const firebaseConfig = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: "",
};

window.baisedFirebase = {
  firebaseConfig,
  app: null,
  auth: null,
  db: null,
};
