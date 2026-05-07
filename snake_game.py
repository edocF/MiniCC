#!/usr/bin/env python3
"""
贪吃蛇小游戏 - 使用 Python 标准库 turtle 模块实现
"""

import turtle
import random
import time

# 游戏常量设置
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 600
GRID_SIZE = 20
SNAKE_SPEED = 150  # 毫秒

# 颜色配置
COLOR_SNAKE_HEAD = "green"
COLOR_SNAKE_BODY = "darkgreen"
COLOR_FOOD = "red"
COLOR_BACKGROUND = "black"
COLOR_TEXT = "white"


class Snake:
    """蛇类 - 管理蛇的位置、移动和身体"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置蛇的状态"""
        self.segments = []
        self.direction = "Right"
        self.score = 0
        self.game_over = False
        
        # 初始位置在屏幕中央
        start_x = 0
        start_y = 0
        
        # 创建初始的三段蛇身
        for i in range(3):
            segment = turtle.Turtle()
            segment.shape("square")
            segment.color(COLOR_SNAKE_BODY)
            segment.penup()
            segment.goto(start_x - i * GRID_SIZE, start_y)
            self.segments.append(segment)
        
        # 更新头部位置
        self.update_head_position()
    
    def update_head_position(self):
        """根据方向更新头部位置"""
        head = self.segments[0]
        x, y = head.xcor(), head.ycor()
        
        if self.direction == "Up":
            head.sety(y + GRID_SIZE)
        elif self.direction == "Down":
            head.sety(y - GRID_SIZE)
        elif self.direction == "Left":
            head.setx(x - GRID_SIZE)
        elif self.direction == "Right":
            head.setx(x + GRID_SIZE)
    
    def move(self):
        """移动蛇"""
        if self.game_over:
            return
        
        # 更新所有身体段的位置（从尾部开始）
        for seg_idx in range(len(self.segments) - 1, 0, -1):
            new_x = self.segments[seg_idx - 1].xcor()
            new_y = self.segments[seg_idx - 1].ycor()
            self.segments[seg_idx].goto(new_x, new_y)
        
        # 更新头部位置
        self.update_head_position()
    
    def change_direction(self, new_direction):
        """改变蛇的移动方向（防止反向移动）"""
        opposites = {
            "Up": "Down",
            "Down": "Up",
            "Left": "Right",
            "Right": "Left"
        }
        
        # 不允许直接反向
        if opposites.get(new_direction) != self.direction:
            self.direction = new_direction
    
    def grow(self):
        """蛇吃到食物后增长"""
        tail = self.segments[-1]
        new_segment = turtle.Turtle()
        new_segment.shape("square")
        new_segment.color(COLOR_SNAKE_BODY)
        new_segment.penup()
        new_segment.goto(tail.xcor(), tail.ycor())
        self.segments.append(new_segment)
    
    def check_collision_with_self(self):
        """检查是否与自身碰撞"""
        head = self.segments[0]
        head_x, head_y = head.xcor(), head.ycor()
        
        # 检查身体部分（跳过头部）
        for segment in self.segments[1:]:
            seg_x, seg_y = segment.xcor(), segment.ycor()
            if abs(head_x - seg_x) < GRID_SIZE and abs(head_y - seg_y) < GRID_SIZE:
                return True
        return False
    
    def check_collision_with_wall(self, screen_width, screen_height):
        """检查是否撞到墙壁"""
        head = self.segments[0]
        x, y = head.xcor(), head.ycor()
        
        half_width = screen_width // 2
        half_height = screen_height // 2
        
        if (x > half_width - GRID_SIZE or x < -half_width + GRID_SIZE or
            y > half_height - GRID_SIZE or y < -half_height + GRID_SIZE):
            return True
        return False


class Food:
    """食物类 - 管理食物的生成和显示"""
    
    def __init__(self):
        self.food = None
        self.spawn()
    
    def spawn(self):
        """生成新的食物"""
        if self.food is None:
            self.food = turtle.Turtle()
            self.food.shape("circle")
            self.food.color(COLOR_FOOD)
            self.food.penup()
        
        # 随机位置（确保在网格上）
        max_x = (SCREEN_WIDTH // 2) - GRID_SIZE
        max_y = (SCREEN_HEIGHT // 2) - GRID_SIZE
        
        random_x = round(random.randint(-max_x, max_x) / GRID_SIZE) * GRID_SIZE
        random_y = round(random.randint(-max_y, max_y) / GRID_SIZE) * GRID_SIZE
        
        self.food.goto(random_x, random_y)
    
    def is_eaten(self, snake_segments):
        """检查食物是否被吃掉"""
        head = snake_segments[0]
        food_x, food_y = self.food.xcor(), self.food.ycor()
        head_x, head_y = head.xcor(), head.ycor()
        
        distance = ((head_x - food_x) ** 2 + (head_y - food_y) ** 2) ** 0.5
        return distance < GRID_SIZE / 2


class Game:
    """游戏主类 - 管理游戏循环和状态"""
    
    def __init__(self):
        self.setup_screen()
        self.snake = Snake()
        self.food = Food()
        self.setup_scoreboard()
        self.setup_controls()
    
    def setup_screen(self):
        """设置游戏窗口"""
        self.screen = turtle.Screen()
        self.screen.title("贪吃蛇游戏")
        self.screen.bgcolor(COLOR_BACKGROUND)
        self.screen.setup(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.screen.tracer(0)  # 关闭自动刷新
    
    def setup_scoreboard(self):
        """设置分数板"""
        self.score_board = turtle.Turtle()
        self.score_board.speed(0)
        self.score_board.shape("square")
        self.score_board.color(COLOR_TEXT)
        self.score_board.penup()
        self.score_board.hideturtle()
        self.score_board.goto(0, SCREEN_HEIGHT // 2 - 30)
        self.update_score()
    
    def update_score(self):
        """更新分数显示"""
        self.score_board.clear()
        self.score_board.write(
            f"Score: {self.snake.score}",
            align="center",
            font=("Arial", 24, "normal")
        )
    
    def setup_controls(self):
        """设置键盘控制"""
        self.screen.listen()
        self.screen.onkey(lambda: self.snake.change_direction("Up"), "Up")
        self.screen.onkey(lambda: self.snake.change_direction("Down"), "Down")
        self.screen.onkey(lambda: self.snake.change_direction("Left"), "Left")
        self.screen.onkey(lambda: self.snake.change_direction("Right"), "Right")
        self.screen.onkey(self.restart_game, "r")
    
    def restart_game(self):
        """重新开始游戏"""
        self.snake.reset()
        self.food.spawn()
        self.snake.game_over = False
        self.update_score()
    
    def check_food_eaten(self):
        """检查是否吃到食物"""
        if self.food.is_eaten(self.snake.segments):
            self.snake.grow()
            self.snake.score += 10
            self.update_score()
            self.food.spawn()
    
    def check_collisions(self):
        """检查碰撞"""
        if self.snake.check_collision_with_self():
            self.game_over()
            return True
        
        if self.snake.check_collision_with_wall(SCREEN_WIDTH, SCREEN_HEIGHT):
            self.game_over()
            return True
        
        return False
    
    def game_over(self):
        """游戏结束处理"""
        self.snake.game_over = True
        self.screen.clear()
        self.screen.bgcolor(COLOR_BACKGROUND)
        
        end_text = turtle.Turtle()
        end_text.speed(0)
        end_text.color("red")
        end_text.penup()
        end_text.hideturtle()
        end_text.goto(0, 0)
        end_text.write(
            "GAME OVER!\n\nFinal Score: {}\nPress 'R' to Restart".format(self.snake.score),
            align="center",
            font=("Arial", 24, "normal")
        )
    
    def run(self):
        """运行游戏主循环"""
        while True:
            if not self.snake.game_over:
                self.snake.move()
                self.check_food_eaten()
                self.check_collisions()
            
            self.screen.update()
            time.sleep(SNAKE_SPEED / 1000)


def main():
    """主函数"""
    print("=" * 50)
    print("欢迎玩贪吃蛇游戏！")
    print("=" * 50)
    print("控制说明:")
    print("  ↑ ↓ ← → : 控制蛇的移动方向")
    print("  R : 重新开始游戏")
    print("=" * 50)
    print("点击游戏窗口开始游戏...")
    
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
