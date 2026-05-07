#!/usr/bin/env python3
"""
贪吃蛇游戏测试用例
使用 Python 标准库 unittest 进行测试
"""

import unittest
from snake_game import Snake, Food, GRID_SIZE


class TestSnake(unittest.TestCase):
    """蛇类测试"""
    
    def setUp(self):
        """每个测试前的准备工作"""
        self.snake = Snake()
    
    def test_initial_position(self):
        """测试初始位置"""
        # 蛇头应该在 (0, 0)
        head = self.snake.segments[0]
        self.assertAlmostEqual(head.xcor(), 0, places=1)
        self.assertAlmostEqual(head.ycor(), 0, places=1)
    
    def test_initial_segments_count(self):
        """测试初始身体段数量"""
        self.assertEqual(len(self.snake.segments), 3)
    
    def test_direction_change_up(self):
        """测试向上移动"""
        self.snake.change_direction("Up")
        self.assertEqual(self.snake.direction, "Up")
        
        # 移动后 y 坐标应该增加
        initial_y = self.snake.segments[0].ycor()
        self.snake.move()
        new_y = self.snake.segments[0].ycor()
        self.assertEqual(new_y, initial_y + GRID_SIZE)
    
    def test_direction_change_down(self):
        """测试向下移动"""
        self.snake.change_direction("Down")
        self.assertEqual(self.snake.direction, "Down")
        
        # 移动后 y 坐标应该减少
        initial_y = self.snake.segments[0].ycor()
        self.snake.move()
        new_y = self.snake.segments[0].ycor()
        self.assertEqual(new_y, initial_y - GRID_SIZE)
    
    def test_direction_change_left(self):
        """测试向左移动"""
        self.snake.change_direction("Left")
        self.assertEqual(self.snake.direction, "Left")
        
        # 移动后 x 坐标应该减少
        initial_x = self.snake.segments[0].xcor()
        self.snake.move()
        new_x = self.snake.segments[0].xcor()
        self.assertEqual(new_x, initial_x - GRID_SIZE)
    
    def test_direction_change_right(self):
        """测试向右移动"""
        self.snake.change_direction("Right")
        self.assertEqual(self.snake.direction, "Right")
        
        # 移动后 x 坐标应该增加
        initial_x = self.snake.segments[0].xcor()
        self.snake.move()
        new_x = self.snake.segments[0].xcor()
        self.assertEqual(new_x, initial_x + GRID_SIZE)
    
    def test_cannot_reverse_direction(self):
        """测试不能直接反向移动"""
        # 初始方向是 Right
        self.assertEqual(self.snake.direction, "Right")
        
        # 尝试反向到 Left，应该无效
        self.snake.change_direction("Left")
        self.assertEqual(self.snake.direction, "Right")
        
        # 尝试转向 Up，应该有效
        self.snake.change_direction("Up")
        self.assertEqual(self.snake.direction, "Up")
        
        # 再尝试反向到 Down，应该无效
        self.snake.change_direction("Down")
        self.assertEqual(self.snake.direction, "Up")
    
    def test_grow(self):
        """测试蛇增长"""
        initial_length = len(self.snake.segments)
        self.snake.grow()
        self.assertEqual(len(self.snake.segments), initial_length + 1)
    
    def test_check_collision_with_self_false(self):
        """测试没有与自身碰撞的情况"""
        # 初始状态下不应该碰撞
        self.assertFalse(self.snake.check_collision_with_self())
    
    def test_check_collision_with_self_true(self):
        """测试与自身碰撞的情况"""
        # 手动设置头部位置接近身体段
        self.snake.segments[0].goto(0, 0)
        self.snake.segments[1].goto(GRID_SIZE, 0)
        self.snake.segments[2].goto(GRID_SIZE * 2, 0)
        
        # 让头部移动到身体段的位置
        self.snake.segments[0].goto(GRID_SIZE, 0)
        
        self.assertTrue(self.snake.check_collision_with_self())
    
    def test_check_collision_with_wall_true(self):
        """测试撞墙情况"""
        # 将蛇头移到屏幕边缘外
        self.snake.segments[0].goto(SCREEN_WIDTH // 2 + 100, 0)
        
        self.assertTrue(self.snake.check_collision_with_wall(SCREEN_WIDTH, SCREEN_HEIGHT))
    
    def test_check_collision_with_wall_false(self):
        """测试未撞墙情况"""
        # 在屏幕中央，不应该撞墙
        self.snake.segments[0].goto(0, 0)
        
        self.assertFalse(self.snake.check_collision_with_wall(SCREEN_WIDTH, SCREEN_HEIGHT))
    
    def test_reset(self):
        """测试重置功能"""
        # 先增长蛇并改变方向
        self.snake.grow()
        self.snake.change_direction("Up")
        self.snake.score = 100
        
        # 重置
        self.snake.reset()
        
        # 验证状态恢复
        self.assertEqual(len(self.snake.segments), 3)
        self.assertEqual(self.snake.direction, "Right")
        self.assertEqual(self.snake.score, 0)


class TestFood(unittest.TestCase):
    """食物类测试"""
    
    def setUp(self):
        """每个测试前的准备工作"""
        self.food = Food()
    
    def test_food_spawned(self):
        """测试食物已生成"""
        self.assertIsNotNone(self.food.food)
    
    def test_food_color(self):
        """测试食物颜色"""
        self.assertEqual(self.food.food.color()[0], "red")
    
    def test_food_is_circle(self):
        """测试食物形状是圆形"""
        self.assertEqual(self.food.food.shape(), "circle")
    
    def test_food_random_position(self):
        """测试食物随机位置"""
        # 第一次生成的位置
        pos1 = (self.food.food.xcor(), self.food.food.ycor())
        
        # 重新生成
        self.food.spawn()
        pos2 = (self.food.food.xcor(), self.food.food.ycor())
        
        # 位置可能相同也可能不同，但必须在合理范围内
        max_pos = (SCREEN_WIDTH // 2) - GRID_SIZE
        min_pos = -(SCREEN_WIDTH // 2) + GRID_SIZE
        
        self.assertGreaterEqual(pos2[0], min_pos)
        self.assertLessEqual(pos2[0], max_pos)
        self.assertGreaterEqual(pos2[1], min_pos)
        self.assertLessEqual(pos2[1], max_pos)


class TestGameLogic(unittest.TestCase):
    """游戏逻辑测试"""
    
    def setUp(self):
        """每个测试前的准备工作"""
        self.snake = Snake()
        self.food = Food()
    
    def test_food_eaten_detection(self):
        """测试食物被吃掉的检测"""
        # 将蛇头移到食物位置
        food_x = self.food.food.xcor()
        food_y = self.food.food.ycor()
        self.snake.segments[0].goto(food_x, food_y)
        
        self.assertTrue(self.food.is_eaten(self.snake.segments))
    
    def test_food_not_eaten(self):
        """测试食物未被吃掉"""
        # 蛇头远离食物
        self.snake.segments[0].goto(0, 0)
        self.food.food.goto(SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT // 2 - 50)
        
        self.assertFalse(self.food.is_eaten(self.snake.segments))
    
    def test_score_increase_on_eat(self):
        """测试吃到食物后分数增加"""
        # 将蛇头移到食物位置
        food_x = self.food.food.xcor()
        food_y = self.food.food.ycor()
        self.snake.segments[0].goto(food_x, food_y)
        
        initial_score = self.snake.score
        if self.food.is_eaten(self.snake.segments):
            self.snake.grow()
            self.snake.score += 10
        
        self.assertEqual(self.snake.score, initial_score + 10)


# 定义全局常量用于测试
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 600


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试
    suite.addTests(loader.loadTestsFromTestCase(TestSnake))
    suite.addTests(loader.loadTestsFromTestCase(TestFood))
    suite.addTests(loader.loadTestsFromTestCase(TestGameLogic))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 60)
    print("开始运行贪吃蛇游戏测试用例")
    print("=" * 60)
    
    success = run_tests()
    
    print("=" * 60)
    if success:
        print("✓ 所有测试通过!")
    else:
        print("✗ 部分测试失败")
    print("=" * 60)
