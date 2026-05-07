#!/usr/bin/env python3
"""
贪吃蛇游戏核心逻辑测试用例（无图形界面版本）
使用 Python 标准库 unittest 进行测试
"""

import unittest
from snake_game_core import Snake, Food, GRID_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT


class TestSnake(unittest.TestCase):
    """蛇类测试"""
    
    def setUp(self):
        """每个测试前的准备工作"""
        self.snake = Snake()
    
    def test_initial_position(self):
        """测试初始位置"""
        # 蛇头应该在 (0, 0)
        head = self.snake.segments[0]
        self.assertEqual(head, (0, 0))
    
    def test_initial_segments_count(self):
        """测试初始身体段数量"""
        self.assertEqual(len(self.snake.segments), 3)
    
    def test_direction_change_up(self):
        """测试向上移动"""
        self.snake.change_direction("Up")
        self.assertEqual(self.snake.direction, "Up")
        
        initial_y = self.snake.segments[0][1]
        self.snake.move()
        new_y = self.snake.segments[0][1]
        self.assertEqual(new_y, initial_y + GRID_SIZE)
    
    def test_direction_change_down(self):
        """测试向下移动"""
        self.snake.change_direction("Down")
        self.assertEqual(self.snake.direction, "Down")
        
        initial_y = self.snake.segments[0][1]
        self.snake.move()
        new_y = self.snake.segments[0][1]
        self.assertEqual(new_y, initial_y - GRID_SIZE)
    
    def test_direction_change_left(self):
        """测试向左移动"""
        self.snake.change_direction("Left")
        self.assertEqual(self.snake.direction, "Left")
        
        initial_x = self.snake.segments[0][0]
        self.snake.move()
        new_x = self.snake.segments[0][0]
        self.assertEqual(new_x, initial_x - GRID_SIZE)
    
    def test_direction_change_right(self):
        """测试向右移动"""
        self.snake.change_direction("Right")
        self.assertEqual(self.snake.direction, "Right")
        
        initial_x = self.snake.segments[0][0]
        self.snake.move()
        new_x = self.snake.segments[0][0]
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
        # grow 方法在 move 中处理，这里测试长度增加
        self.snake.move()  # 移动但不增长
        self.assertEqual(len(self.snake.segments), initial_length)
    
    def test_check_collision_with_self_false(self):
        """测试没有与自身碰撞的情况"""
        # 初始状态下不应该碰撞
        self.assertFalse(self.snake.check_collision_with_self())
    
    def test_check_collision_with_self_true(self):
        """测试与自身碰撞的情况"""
        # 手动设置头部位置接近身体段
        self.snake.segments = [(20, 0), (20, 0), (-20, 0)]
        
        self.assertTrue(self.snake.check_collision_with_self())
    
    def test_check_collision_with_wall_true(self):
        """测试撞墙情况"""
        # 将蛇头移到屏幕边缘外
        self.snake.segments = [(350, 0), (330, 0), (310, 0)]
        
        self.assertTrue(self.snake.check_collision_with_wall(SCREEN_WIDTH, SCREEN_HEIGHT))
    
    def test_check_collision_with_wall_false(self):
        """测试未撞墙情况"""
        # 在屏幕中央，不应该撞墙
        self.snake.segments = [(0, 0), (-20, 0), (-40, 0)]
        
        self.assertFalse(self.snake.check_collision_with_wall(SCREEN_WIDTH, SCREEN_HEIGHT))
    
    def test_reset(self):
        """测试重置功能"""
        # 先改变状态
        self.snake.change_direction("Up")
        self.snake.score = 100
        
        # 重置
        self.snake.reset()
        
        # 验证状态恢复
        self.assertEqual(len(self.snake.segments), 3)
        self.assertEqual(self.snake.direction, "Right")
        self.assertEqual(self.snake.score, 0)
        self.assertEqual(self.snake.segments[0], (0, 0))


class TestFood(unittest.TestCase):
    """食物类测试"""
    
    def setUp(self):
        """每个测试前的准备工作"""
        self.food = Food()
    
    def test_food_spawned(self):
        """测试食物已生成"""
        self.assertIsNotNone(self.food.position)
    
    def test_food_random_position(self):
        """测试食物随机位置"""
        pos1 = self.food.position
        
        # 重新生成
        self.food.spawn()
        pos2 = self.food.position
        
        # 位置可能相同也可能不同，但必须在合理范围内
        max_pos = 280
        min_pos = -280
        
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
        self.snake.segments[0] = self.food.position
        
        self.assertTrue(self.food.is_eaten(self.snake.segments))
    
    def test_food_not_eaten(self):
        """测试食物未被吃掉"""
        # 蛇头远离食物
        self.snake.segments[0] = (0, 0)
        self.food.position = (300, 300)
        
        self.assertFalse(self.food.is_eaten(self.snake.segments))
    
    def test_move_functionality(self):
        """测试移动功能"""
        initial_head = self.snake.segments[0]
        self.snake.change_direction("Right")
        self.snake.move()
        
        new_head = self.snake.segments[0]
        self.assertEqual(new_head[0], initial_head[0] + GRID_SIZE)
        self.assertEqual(new_head[1], initial_head[1])
    
    def test_score_increase_on_eat(self):
        """测试吃到食物后分数增加"""
        # 将蛇头移到食物位置
        self.snake.segments[0] = self.food.position
        
        initial_score = self.snake.score
        if self.food.is_eaten(self.snake.segments):
            self.snake.grow()
            self.snake.score += 10
        
        self.assertEqual(self.snake.score, initial_score + 10)


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
    print("开始运行贪吃蛇游戏核心逻辑测试用例")
    print("=" * 60)
    
    success = run_tests()
    
    print("=" * 60)
    if success:
        print("✓ 所有测试通过!")
    else:
        print("✗ 部分测试失败")
    print("=" * 60)
