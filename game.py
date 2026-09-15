import math
import random
import sys

import pygame


pygame.init()

WIDTH, HEIGHT = 1280, 720
FPS = 60
START_X = 180
COURSE_DISTANCE = 1000
WORLD_DISTANCE = 3600
FINISH_X = START_X + WORLD_DISTANCE
WORLD_LENGTH = FINISH_X + 220
GROUND_Y = 500

SKY = (246, 194, 115)
SAND = (224, 157, 79)
SAND_LIGHT = (241, 181, 99)
SAND_DARK = (164, 99, 54)
INK = (48, 38, 34)
WHITE = (255, 247, 225)
RED = (188, 54, 42)
GREEN = (54, 132, 76)


def make_terrain():
	points = []
	for x in range(-300, WORLD_LENGTH + WIDTH, 24):
		height = (
			math.sin(x * 0.008) * 42
			+ math.sin(x * 0.021 + 1.7) * 22
			+ math.sin(x * 0.0035) * 70
		)
		points.append((x, GROUND_Y - height))
	return points


def terrain_y(terrain, world_x):
	index = max(0, min(len(terrain) - 2, int((world_x + 300) / 24)))
	left_x, left_y = terrain[index]
	right_x, right_y = terrain[index + 1]
	ratio = (world_x - left_x) / (right_x - left_x)
	return left_y + (right_y - left_y) * ratio


def draw_text(surface, text, position, font, color=INK, anchor="topleft"):
	image = font.render(text, True, color)
	rect = image.get_rect(**{anchor: position})
	surface.blit(image, rect)


class Vehicle:
	def __init__(self):
		self.reset()

	def reset(self):
		self.x = float(START_X)
		self.y = 400.0
		self.velocity_x = 0.0
		self.velocity_y = 0.0
		self.angle = 0.0
		self.angular_velocity = 0.0
		self.fuel = 100.0
		self.distance = 0
		self.alive = True

	@property
	def rect(self):
		return pygame.Rect(int(self.x - 30), int(self.y - 45), 60, 32)

	def update(self, keys, terrain, dt):
		acceleration = 0.0
		if keys[pygame.K_d] or keys[pygame.K_w]:
			acceleration += 250.0
		if keys[pygame.K_a]:
			acceleration -= 150.0
		if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
			boost_direction = -1.0 if keys[pygame.K_a] or self.velocity_x < -5 else 1.0
			acceleration += 90.0 * boost_direction

		# Uphill slopes resist motion; downhill slopes add momentum.
		slope = (terrain_y(terrain, self.x + 24) - terrain_y(terrain, self.x - 24)) / 48
		acceleration += max(-210.0, min(210.0, slope * 180.0))
		self.velocity_x += acceleration * dt
		self.velocity_x *= 0.992 ** (dt * FPS)
		self.velocity_x = max(-130.0, min(360.0, self.velocity_x))
		self.velocity_y += 850.0 * dt
		self.x += self.velocity_x * dt
		self.y += self.velocity_y * dt

		ground = terrain_y(terrain, self.x)
		if self.y + 8 >= ground:
			self.y = ground - 8
			self.velocity_y = min(0.0, self.velocity_y * -0.22)
			target_angle = math.atan2(slope, 1.0)
			angle_error = (target_angle - self.angle + math.pi) % math.tau - math.pi
			self.angular_velocity += angle_error * 55.0 * dt
			self.angular_velocity *= 0.72 ** (dt * FPS)
			self.angle += self.angular_velocity * dt
		else:
			self.angle += self.angular_velocity * dt

		self.fuel -= (0.7 + max(0.0, self.velocity_x) * 0.004) * dt
		self.fuel = max(0.0, self.fuel)
		progress = (self.x - START_X) / WORLD_DISTANCE
		self.distance = max(0, min(COURSE_DISTANCE, int(progress * COURSE_DISTANCE)))

	def draw(self, surface, camera_x):
		body = pygame.Surface((100, 64), pygame.SRCALPHA)
		pygame.draw.polygon(body, (29, 91, 104), [(16, 39), (26, 17), (63, 14), (83, 31), (86, 44), (12, 44)])
		pygame.draw.polygon(body, (225, 181, 85), [(34, 18), (47, 6), (63, 14), (61, 22)])
		pygame.draw.circle(body, (66, 43, 32), (48, 14), 6)
		pygame.draw.line(body, WHITE, (20, 34), (78, 30), 3)
		pygame.draw.circle(body, INK, (25, 49), 12)
		pygame.draw.circle(body, INK, (76, 49), 12)
		pygame.draw.circle(body, (210, 205, 186), (25, 49), 5)
		pygame.draw.circle(body, (210, 205, 186), (76, 49), 5)
		rotated = pygame.transform.rotate(body, -math.degrees(self.angle))
		rect = rotated.get_rect(center=(int(self.x - camera_x), int(self.y - 22)))
		surface.blit(rotated, rect)


class Game:
	def __init__(self):
		self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
		pygame.display.set_caption("Desert Climb Racing")
		self.clock = pygame.time.Clock()
		self.title_font = pygame.font.Font(None, 48)
		self.large_font = pygame.font.Font(None, 76)
		self.font = pygame.font.Font(None, 28)
		self.small_font = pygame.font.Font(None, 22)
		self.terrain = make_terrain()
		self.rng = random.Random(19)
		self.reset()

	def reset(self):
		self.vehicle = Vehicle()
		self.camera_x = 0.0
		self.state = "playing"
		self.message = ""
		self.pickups = [x for x in range(700, FINISH_X - 200, 1000)]
		self.settlements = [x for x in range(1200, FINISH_X - 100, 1450)]
		self.hazards = [x for x in range(850, FINISH_X - 100, 700)]
		self.collected = set()
		self.hit_hazards = set()

	def update(self, keys, dt):
		if self.state != "playing":
			return
		self.vehicle.update(keys, self.terrain, dt)
		self.camera_x = max(0.0, min(WORLD_LENGTH - WIDTH, self.vehicle.x - 260))

		for index, pickup_x in enumerate(self.pickups):
			if index not in self.collected and abs(self.vehicle.x - pickup_x) < 52:
				self.collected.add(index)
				self.vehicle.fuel = min(100.0, self.vehicle.fuel + 30.0)

		for index, hazard_x in enumerate(self.hazards):
			if index not in self.hit_hazards and abs(self.vehicle.x - hazard_x) < 34:
				self.hit_hazards.add(index)
				self.vehicle.velocity_x *= 0.35
				self.vehicle.fuel = max(0.0, self.vehicle.fuel - 12)

		if self.vehicle.fuel <= 0:
			self.state = "lost"
			self.message = "You ran out of fuel in the desert."
		elif self.vehicle.x >= FINISH_X:
			self.state = "won"
			self.message = "You crossed the desert!"

	def draw_background(self):
		self.screen.fill(SKY)
		for layer, color, amplitude, base_y in [(0, (232, 165, 91), 30, 320), (1, (215, 138, 74), 44, 390)]:
			points = []
			for x in range(-40, WIDTH + 80, 35):
				world_x = x + self.camera_x * (0.15 + layer * 0.1)
				points.append((x, base_y + math.sin(world_x * 0.009) * amplitude + math.sin(world_x * 0.02) * 13))
			points += [(WIDTH, HEIGHT), (0, HEIGHT)]
			pygame.draw.polygon(self.screen, color, points)
		pygame.draw.circle(self.screen, (255, 221, 139), (WIDTH - 150, 125), 55)

	def draw_world(self):
		terrain_points = [(int(x - self.camera_x), int(y)) for x, y in self.terrain if -30 < x - self.camera_x < WIDTH + 30]
		if len(terrain_points) > 1:
			pygame.draw.polygon(self.screen, SAND, terrain_points + [(WIDTH, HEIGHT), (0, HEIGHT)])
			pygame.draw.lines(self.screen, SAND_LIGHT, False, terrain_points, 5)

		for x in self.pickups:
			screen_x = int(x - self.camera_x)
			if -30 < screen_x < WIDTH + 30:
				index = self.pickups.index(x)
				if index not in self.collected:
					y = terrain_y(self.terrain, x) - 58
					pygame.draw.circle(self.screen, (119, 76, 35), (screen_x, int(y)), 22)
					pygame.draw.rect(self.screen, (218, 45, 37), (screen_x - 14, int(y) - 16, 28, 32), border_radius=5)
					pygame.draw.rect(self.screen, (157, 28, 27), (screen_x - 9, int(y) - 21, 18, 7), border_radius=2)
					pygame.draw.rect(self.screen, (255, 116, 75), (screen_x - 9, int(y) - 11, 5, 20), border_radius=2)

		for x in self.hazards:
			screen_x = int(x - self.camera_x)
			if -40 < screen_x < WIDTH + 40:
				y = terrain_y(self.terrain, x)
				pygame.draw.polygon(self.screen, SAND_DARK, [(screen_x - 19, y), (screen_x, y - 28), (screen_x + 19, y)])
				pygame.draw.line(self.screen, (116, 63, 42), (screen_x - 12, y - 3), (screen_x + 10, y - 22), 4)

		for x in self.settlements:
			screen_x = int(x - self.camera_x)
			if -150 < screen_x < WIDTH + 150:
				y = terrain_y(self.terrain, x)
				pygame.draw.rect(self.screen, (180, 106, 57), (screen_x - 42, y - 56, 84, 56))
				pygame.draw.polygon(self.screen, (126, 73, 48), [(screen_x - 50, y - 56), (screen_x, y - 91), (screen_x + 50, y - 56)])
				pygame.draw.rect(self.screen, (90, 54, 42), (screen_x - 10, y - 31, 20, 31))
				pygame.draw.circle(self.screen, (50, 119, 76), (screen_x + 70, int(y - 72)), 17)
				pygame.draw.line(self.screen, (74, 83, 43), (screen_x + 70, y - 60), (screen_x + 70, y), 5)

		finish_x = int(FINISH_X - self.camera_x)
		if -100 < finish_x < WIDTH + 100:
			y = terrain_y(self.terrain, FINISH_X)
			pygame.draw.line(self.screen, INK, (finish_x, y - 130), (finish_x, y), 5)
			pygame.draw.polygon(self.screen, WHITE, [(finish_x, y - 130), (finish_x + 62, y - 112), (finish_x, y - 94)])
			draw_text(self.screen, "FINISH", (finish_x + 4, y - 164), self.small_font, INK, "midtop")

		self.vehicle.draw(self.screen, self.camera_x)

	def draw_hud(self):
		pygame.draw.rect(self.screen, (255, 237, 191), (22, 20, 390, 100), border_radius=12)
		draw_text(self.screen, "DESERT CLIMB", (42, 31), self.title_font, INK)
		draw_text(self.screen, f"Distance  {self.vehicle.distance:04d} m", (42, 77), self.small_font, INK)
		draw_text(self.screen, "FUEL", (450, 30), self.small_font, INK)
		pygame.draw.rect(self.screen, INK, (450, 58, 270, 24), border_radius=6)
		fuel_width = int(264 * self.vehicle.fuel / 100)
		fuel_color = GREEN if self.vehicle.fuel > 30 else RED
		pygame.draw.rect(self.screen, fuel_color, (453, 61, fuel_width, 18), border_radius=4)
		draw_text(self.screen, f"{int(self.vehicle.fuel)}%", (735, 58), self.font, INK)
		draw_text(self.screen, "W/D drive   A brake/reverse   SHIFT boost", (WIDTH - 28, 31), self.small_font, INK, "topright")

	def draw_overlay(self):
		if self.state == "playing":
			return
		veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		veil.fill((36, 27, 25, 135))
		self.screen.blit(veil, (0, 0))
		heading = "DESERT CONQUERED" if self.state == "won" else "JOURNEY OVER"
		color = (255, 220, 119) if self.state == "won" else (255, 157, 105)
		draw_text(self.screen, heading, (WIDTH // 2, 255), self.large_font, color, "midtop")
		draw_text(self.screen, self.message, (WIDTH // 2, 350), self.font, WHITE, "midtop")
		draw_text(self.screen, f"Final distance: {self.vehicle.distance} m", (WIDTH // 2, 390), self.font, WHITE, "midtop")
		draw_text(self.screen, "Press R to ride again or ESC to quit", (WIDTH // 2, 465), self.font, WHITE, "midtop")

	def run(self):
		running = True
		while running:
			dt = min(self.clock.tick(FPS) / 1000.0, 0.04)
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					running = False
				elif event.type == pygame.KEYDOWN:
					if event.key == pygame.K_ESCAPE:
						running = False
					elif event.key == pygame.K_r and self.state != "playing":
						self.reset()

			self.update(pygame.key.get_pressed(), dt)
			self.draw_background()
			self.draw_world()
			self.draw_hud()
			self.draw_overlay()
			pygame.display.flip()

		pygame.quit()
		sys.exit()


if __name__ == "__main__":
	Game().run()