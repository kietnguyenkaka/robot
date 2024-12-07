import gym
from gym import spaces
import numpy as np

class SpeechCorrectionEnv(gym.Env):
    def __init__(self):
        super(SpeechCorrectionEnv, self).__init__()
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(10,), dtype=np.float32)
        self.action_space = spaces.Discrete(3)
        self.state = np.random.uniform(-1, 1, size=(10,))
        self.correct_responses = 0

    def reset(self):
        self.state = np.random.uniform(-1, 1, size=(10,))
        self.correct_responses = 0
        return self.state

    def step(self, action):
        reward = -1 if action == 0 else np.random.choice([1, -1], p=[0.8, 0.2])
        self.state = np.random.uniform(-1, 1, size=(10,))
        done = self.correct_responses >= 10
        if reward > 0:
            self.correct_responses += 1
        else:
            self.correct_responses = 0
        return self.state, reward, done, {}

    def render(self, mode='human'):
        print(f"State: {self.state}, Correct Responses: {self.correct_responses}")

print(dir())

