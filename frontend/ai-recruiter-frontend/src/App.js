import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { FontLoader } from 'three/examples/jsm/loaders/FontLoader';
import { TextGeometry } from 'three/examples/jsm/geometries/TextGeometry';
import Dashboard from './Dashboard';
import VideoInterview from './VideoInterview';
import MockInterview from './MockInterview';
import ParticlesBackground from "./ParticlesBackground"; // Import the background
import './App.css';

function ThreeJsAnimation({ onAnimationComplete }) {
  const mountRef = useRef(null);

  useEffect(() => {
    // Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      75,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    // Particles
    const particlesGeometry = new THREE.BufferGeometry();
    const particlesCount = 1500; // Increased particle count for density
    const particlesPositions = new Float32Array(particlesCount * 3);

    for (let i = 0; i < particlesCount * 3; i++) {
      particlesPositions[i] = (Math.random() - 0.5) * 50; // Spread particles randomly in space
    }

    particlesGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(particlesPositions, 3)
    );

    const particlesMaterial = new THREE.PointsMaterial({
      size: 0.1,
      color: 0x3498db, // Particle color set to #3498db
      transparent: true,
      opacity: 0.8,
    });

    const particles = new THREE.Points(particlesGeometry, particlesMaterial);
    scene.add(particles);

    // Camera Position
    camera.position.z = 15;

    // Text
    const fontLoader = new FontLoader();
    fontLoader.load(
      "https://threejs.org/examples/fonts/helvetiker_regular.typeface.json",
      (font) => {
        const textGeometry = new TextGeometry("AI Recruiter", {
          font: font,
          size: 2, // Increased text size
          height: 0.3, // Adjusted height for better depth
        });
        const textMaterial = new THREE.MeshStandardMaterial({
          color: 0x3498db, // Text color set to #3498db
          emissive: 0x1e90ff, // Subtle glow effect
          emissiveIntensity: 0.9,
        });
        const textMesh = new THREE.Mesh(textGeometry, textMaterial);

        // Compute bounding box to center the text
        textGeometry.computeBoundingBox();
        const boundingBox = textGeometry.boundingBox;
        const textWidth = boundingBox.max.x - boundingBox.min.x;
        const textHeight = boundingBox.max.y - boundingBox.min.y;

        // Center the text
        textMesh.position.set(-textWidth / 2, -textHeight / 2, -10);

        scene.add(textMesh);

        // Animation
        const startTime = performance.now();
        const duration = 2000;

        const animateText = (time) => {
          const elapsed = time - startTime;
          const progress = Math.min(elapsed / duration, 1);

          // Smooth easing function for animation
          const easeOutExpo = (t) =>
            t === 1 ? 1 : 1 - Math.pow(2, -10 * t);

          const easedProgress = easeOutExpo(progress);

          // Animate text movement and scaling
          textMesh.position.z = -10 + easedProgress * 10;
          textMesh.scale.setScalar(0.5 + easedProgress * 0.5);

          // Stop animation when complete
          if (progress < 1) {
            requestAnimationFrame(animateText);
          } else {
            onAnimationComplete();
          }
        };

        requestAnimationFrame(animateText);
      },
      undefined, // onProgress
      (error) => {
        console.error("Font loading failed:", error);
      }
    );

    // Particles Animation
    let animationId;
    const animate = () => {
      const positions = particlesGeometry.attributes.position.array;

      for (let i = 0; i < particlesCount * 3; i += 3) {
        positions[i + 1] += 0.02 * Math.sin(i + Date.now() * 0.001); // Float particles up and down
        positions[i] += 0.01 * Math.sin(i + Date.now() * 0.001); // Horizontal drifting
        if (positions[i + 1] > 25) {
          positions[i + 1] = -25; // Reset Y position if out of bounds
        }
      }
      particlesGeometry.attributes.position.needsUpdate = true; // Update the particle positions

      renderer.render(scene, camera);
      animationId = requestAnimationFrame(animate);
    };
    animate();

    // Cleanup
    return () => {
      cancelAnimationFrame(animationId);
      if (mountRef.current && mountRef.current.contains(renderer.domElement)) {
        mountRef.current.removeChild(renderer.domElement);
      }
    };
  }, [onAnimationComplete]);

  return <div ref={mountRef} style={{ width: "100%", height: "100vh" }}></div>;
}

function App() {
  const [showLandingAnimation, setShowLandingAnimation] = useState(true); // Track landing animation state
  const [activeTab, setActiveTab] = useState('mockinterview');

  const handleAnimationComplete = () => {
    setShowLandingAnimation(false); // Hide landing animation after 2 seconds
  };

  return (
    <>
      {/* Render Landing Animation or Main App */}
      {showLandingAnimation ? (
        <ThreeJsAnimation onAnimationComplete={handleAnimationComplete} />
      ) : (
        <>
          {/* Particles Background */}
          <ParticlesBackground />

          {/* Main App */}
          <div className="app">
            <div className="tab-container">
              <div className="tabs">
                <button
                  className={`tab ${activeTab === 'mockinterview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('mockinterview')}
                >
                  Mock Interview
                </button>
                <button
                  className={`tab ${activeTab === 'dashboard' ? 'active' : ''}`}
                  onClick={() => setActiveTab('dashboard')}
                >
                  Recruiter Dashboard
                </button>
                <button
                  className={`tab ${activeTab === 'interview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('interview')}
                >
                  Video Interview
                </button>
              </div>
            </div>
            <div className="tab-content">
              {activeTab === 'mockinterview' && <MockInterview />}
              {activeTab === 'dashboard' && <Dashboard />}
              {activeTab === 'interview' && <VideoInterview />}
            </div>
            {/* GitHub Logo */}
            <a
              href="https://github.com/kodegod/ai-recruiter"
              target="_blank"
              rel="noopener noreferrer"
              className="github-link"
            >
              <img
                src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
                alt="GitHub Repository"
                className="github-logo"
              />
            </a>
          </div>
        </>
      )}
    </>
  );
}

export default App;