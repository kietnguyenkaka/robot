import numpy as np
from collections import deque
import random
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
from environment import SpeechCorrectionEnv
from model import DQN

# Siêu tham số
gamma = 0.99
epsilon = 1.0
epsilon_decay = 0.995
epsilon_min = 0.1
learning_rate = 0.001
batch_size = 64
memory_size = 10000

# Tạo môi trường và mô hình
env = SpeechCorrectionEnv()
num_actions = env.action_space.n
state_shape = env.observation_space.shape[0]

model = DQN(num_actions)
target_model = DQN(num_actions)
optimizer = Adam(learning_rate)
memory = deque(maxlen=memory_size)

def update_target_model():
    target_model.set_weights(model.get_weights())

def choose_action(state, epsilon):
    if np.random.rand() <= epsilon:
        return np.random.randint(num_actions)
    q_values = model(np.expand_dims(state, axis=0))
    return np.argmax(q_values.numpy())

def train_step(batch):
    states, actions, rewards, next_states, dones = zip(*batch)
    states = np.array(states)
    next_states = np.array(next_states)
    rewards = np.array(rewards)
    dones = np.array(dones, dtype=np.float32)

    future_q_values = target_model(next_states).numpy()
    target_q_values = rewards + gamma * np.max(future_q_values, axis=1) * (1 - dones)

    with tf.GradientTape() as tape:
        q_values = model(states)
        one_hot_actions = tf.one_hot(actions, num_actions)
        predicted_q_values = tf.reduce_sum(q_values * one_hot_actions, axis=1)
        loss = tf.keras.losses.MSE(target_q_values, predicted_q_values)

    gradients = tape.gradient(loss, model.trainable_variables)
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))

num_episodes = 500
target_update_freq = 10

for episode in range(num_episodes):
    state = env.reset()
    total_reward = 0
    for t in range(200):
        action = choose_action(state, epsilon)
        next_state, reward, done, _ = env.step(action)
        memory.append((state, action, reward, next_state, done))
        state = next_state
        total_reward += reward
        if len(memory) > batch_size:
            batch = random.sample(memory, batch_size)
            train_step(batch)
        if done:
            break
    epsilon = max(epsilon * epsilon_decay, epsilon_min)
    if episode % target_update_freq == 0:
        update_target_model()
    print(f"Episode: {episode + 1}, Total Reward: {total_reward}, Epsilon: {epsilon:.2f}")
