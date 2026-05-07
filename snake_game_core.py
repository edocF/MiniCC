#!/usr/bin/env python3
"""
贪吃蛇游戏 - 无图形界面版本（用于测试）
"""

import random


class Snake:
    """蛇类 - 管理蛇的位置、移动和身体（无图形界面版本）"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置蛇的状态"""
        self.segments = [(0, 0), (-20, 0), (-40, 0)]  # 使用坐标元组列表
        self.direction = "Right"
        self.score = 0
        self.game_over = False
    
    def update_head_position(self):
        """根据方向更新头部位置"""
        head_x, head_y = self.segments[0]
        
        if self.direction == "Up":
            self.segments.insert(0, (head_x, head_y + 20))
        elif self.direction == "Down":
            self.segments.insert(0, (head_x, head_y - 20))
        elif self.direction == "Left":
            self.segments.insert(0, (head_x - 20, head_y))
        elif self.direction == "Right":
            self.segments.insert(0, (head_x + 20, head_y))
        
        # 不移除尾部（用于检测是否吃到食物）
    
    def move(self):
        """移动蛇"""
        if self.game_over:
            return
        
        self.update_head_position()
        
        # 如果没有吃到食物，移除尾部
        if len(self.segments) > 3:  # 初始长度为 3
            self.segments.pop()
    
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
        """蛇吃到食物后增长（不移除尾部）"""
        pass  # 在 move 中已经处理了
    
    def check_collision_with_self(self):
        """检查是否与自身碰撞"""
        head = self.segments[0]
        # 检查身体部分（跳过头部）
        for segment in self.segments[1:]:
            if head == segment:
                return True
        return False
    
    def check_collision_with_wall(self, screen_width, screen_height):
        """检查是否撞到墙壁"""
        head = self.segments[0]
        half_width = screen_width // 2
        half_height = screen_height // 2
        
        if (head[0] > half_width - 20 or head[0] < -half_width + 20 or
            head[1] > half_height - 20 or head[1] < -half_height + 20):
            return True
        return False


class Food:
    """食物类 - 管理食物的生成和显示（无图形界面版本）"""
    
    def __init__(self):
        self.position = None
        self.spawn()
    
    def spawn(self):
        """生成新的食物"""
        max_pos = 280
        min_pos = -280
        
        random_x = round(random.randint(min_pos, max_pos) / 20) * 20
        random_y = round(random.randint(min_pos, max_y) / 20) * 20
        self.position = (random_x, random_y)
    
    def is_eaten(self, snake_segments):
        """检查食物是否被吃掉"""
        head = snake_segments[0]
        distance = ((head[0] - self.position[0]) ** 2 + 
                    (head[1] - self.position[1]) ** 2) ** 0.5
        return distance < 15


# 常量定义
GRID_SIZE = 20
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 600
