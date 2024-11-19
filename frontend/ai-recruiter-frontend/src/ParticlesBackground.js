import React, { useEffect, useRef } from "react";
import * as THREE from "three";

function ParticlesBackground() {
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

    // Animation
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
  }, []);

  return (
    <div
      ref={mountRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        zIndex: -1, // Make it stay in the background
        overflow: "hidden",
      }}
    ></div>
  );
}

export default ParticlesBackground;