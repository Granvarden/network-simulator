"""
main.py - NetEngineer 3D Main Entry Point
Realistic First-Person 3D Network Engineer Simulator with Cisco CLI,
Datacenter Cabling, and Step-by-Step Training in Pygame + PyOpenGL.
"""

import sys
import pygame
from engine.game import GameManager

def main():
    pygame.init()
    pygame.font.init()

    try:
        game = GameManager()
        game.run()
    except KeyboardInterrupt:
        print("\nExiting NetEngineer 3D...")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error encountered in NetEngineer 3D: {e}")
    finally:
        pygame.quit()

if __name__ == "__main__":
    main()
