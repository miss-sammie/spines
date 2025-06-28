import React, { useEffect, useRef } from 'react';
import p5 from 'p5';

const CloudSky = ({ children }) => {
  const sketchRef = useRef();
  const p5Instance = useRef();

  useEffect(() => {
    // Prevent double mounting in React StrictMode
    if (p5Instance.current) return;

    const sketch = (p) => {
      let clouds = [];
      let cloudImg = null;
      let imageLoaded = false;
      const numClouds = 16;

      p.setup = async () => {
        try {
          p.createCanvas(p.windowWidth, p.windowHeight);
          
          // Load cloud image using p5.js 2.0 approach
          try {
            cloudImg = await new Promise((resolve, reject) => {
              p.loadImage('/cloud.png', resolve, reject);
            });
            imageLoaded = true;
            console.log('Cloud image loaded successfully');
          } catch (err) {
            console.warn('Could not load cloud image, continuing without clouds:', err);
            imageLoaded = false;
          }
          
          // Initialize clouds with random positions
          for (let i = 0; i < numClouds; i++) {
            clouds.push({
              x: p.random(-200, p.width + 200),
              y: p.random(50, p.height - 200),
              scale: p.random(0.3, 0.8),
              speed: p.random(0.2, 0.6),
              alpha: p.random(100, 180)
            });
          }
        } catch (err) {
          console.error('Error in p5 setup:', err);
        }
      };

      p.draw = () => {
        try {
          // Soft blue sky gradient
          for (let y = 0; y < p.height; y++) {
            const inter = p.map(y, 0, p.height, 0, 1);
            const c = p.lerpColor(
              p.color(135, 206, 235), // Light sky blue
              p.color(176, 224, 230), // Powder blue
              inter
            );
            p.stroke(c);
            p.line(0, y, p.width, y);
          }

          // Draw and animate clouds only if image is loaded
          if (imageLoaded && cloudImg) {
            clouds.forEach((cloud) => {
              p.push();
              p.translate(cloud.x, cloud.y);
              p.scale(cloud.scale);
              p.tint(255, cloud.alpha);
              
              p.image(cloudImg, -cloudImg.width / 2, -cloudImg.height / 2);
              
              p.pop();

              // Move cloud from right to left
              cloud.x -= cloud.speed;

              // Reset cloud position when it goes off screen
              if (cloud.x < -300) {
                cloud.x = p.width + 200;
                cloud.y = p.random(50, p.height - 200);
                cloud.scale = p.random(0.3, 0.8);
                cloud.speed = p.random(0.2, 0.6);
                cloud.alpha = p.random(100, 180);
              }
            });
          }
        } catch (err) {
          console.error('Error in p5 draw:', err);
        }
      };

      p.windowResized = () => {
        try {
          p.resizeCanvas(p.windowWidth, p.windowHeight);
        } catch (err) {
          console.error('Error in p5 windowResized:', err);
        }
      };
    };

    // Create p5 instance with error handling
    try {
      if (sketchRef.current) {
        p5Instance.current = new p5(sketch, sketchRef.current);
      }
    } catch (err) {
      console.error('Error creating p5 instance:', err);
    }

    // Cleanup on unmount
    return () => {
      if (p5Instance.current) {
        try {
          p5Instance.current.remove();
        } catch (err) {
          console.error('Error removing p5 instance:', err);
        }
        p5Instance.current = null;
      }
    };
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div 
        ref={sketchRef} 
        style={{ 
          position: 'absolute', 
          top: 0, 
          left: 0, 
          width: '100%', 
          height: '100%',
          zIndex: 1 
        }} 
      />
      <div 
        style={{ 
          position: 'relative', 
          zIndex: 2,
          width: '100%',
          height: '100%'
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default CloudSky; 