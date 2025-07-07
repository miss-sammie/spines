/**
 * CloudSky.js - Beautiful animated sky background using p5.js
 * Extracted from spines v1.0 and modernized for component architecture
 */

class CloudSky {
    constructor(containerId = 'cloudSky') {
        this.containerId = containerId;
        this.p5Instance = null;
        this.clouds = [];
        this.cloudImg = null;
        this.imageLoaded = false;
        this.numClouds = 8;
        
        this.init();
    }
    
    init() {
        // Create container if it doesn't exist
        if (!document.getElementById(this.containerId)) {
            const container = document.createElement('div');
            container.id = this.containerId;
            document.body.appendChild(container);
        }
        
        // Create p5 sketch
        const sketch = (p) => {
            p.setup = () => {
                try {
                    p.createCanvas(p.windowWidth, p.windowHeight);
                    
                    // Try to load cloud image
                    p.loadImage('/static/cloud.png', 
                        (img) => {
                            this.cloudImg = img;
                            this.imageLoaded = true;
                            console.log('Cloud image loaded successfully');
                        },
                        (err) => {
                            console.warn('Could not load cloud image, continuing without clouds:', err);
                            this.imageLoaded = false;
                        }
                    );
                    
                    // Initialize clouds with random positions
                    for (let i = 0; i < this.numClouds; i++) {
                        this.clouds.push({
                            x: p.random(-200, p.width + 200),
                            y: p.random(50, p.height - 200),
                            scale: p.random(0.3, 0.8),
                            speed: p.random(0.2, 0.6),
                            alpha: p.random(100, 180)
                        });
                    }
                } catch (err) {
                    console.error('Error in CloudSky setup:', err);
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
                    if (this.imageLoaded && this.cloudImg) {
                        this.clouds.forEach((cloud) => {
                            p.push();
                            p.translate(cloud.x, cloud.y);
                            p.scale(cloud.scale);
                            p.tint(255, cloud.alpha);
                            
                            p.image(this.cloudImg, -this.cloudImg.width / 2, -this.cloudImg.height / 2);
                            
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
                    console.error('Error in CloudSky draw:', err);
                }
            };

            p.windowResized = () => {
                try {
                    p.resizeCanvas(p.windowWidth, p.windowHeight);
                } catch (err) {
                    console.error('Error in CloudSky windowResized:', err);
                }
            };
        };

        // Create p5 instance with error handling
        try {
            this.p5Instance = new p5(sketch, this.containerId);
        } catch (err) {
            console.error('Error creating CloudSky p5 instance:', err);
        }
    }
    
    destroy() {
        if (this.p5Instance) {
            try {
                this.p5Instance.remove();
                this.p5Instance = null;
            } catch (err) {
                console.error('Error destroying CloudSky:', err);
            }
        }
    }
    
    // Static method to create and initialize
    static create(containerId) {
        return new CloudSky(containerId);
    }
}

// Auto-initialize if container exists
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('cloudSky')) {
        window.cloudSky = CloudSky.create('cloudSky');
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CloudSky;
} 