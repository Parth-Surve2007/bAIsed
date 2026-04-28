// Firebase client bootstrap.
// Load the Firebase compat SDK via CDN before this file.

const firebaseConfig = {
  apiKey: "AIzaSyCYlDy4ciaxrSRvrqRSIVO5GK4_gyFBkIU",
  authDomain: "baised-3e20d.firebaseapp.com",
  projectId: "baised-3e20d",
  storageBucket: "baised-3e20d.firebasestorage.app",
  messagingSenderId: "430336051200",
  appId: "1:430336051200:web:61303f9f5c0f72589930e5",
  measurementId: "G-TPM6PQG4SX",
};

let app = null;
let auth = null;

if (window.firebase && typeof window.firebase.initializeApp === "function") {
  app = window.firebase.apps && window.firebase.apps.length
    ? window.firebase.app()
    : window.firebase.initializeApp(firebaseConfig);
  auth = window.firebase.auth();
}

window.baisedFirebase = {
  firebaseConfig,
  app,
  auth,
  db: null,
};
