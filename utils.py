import torch

def build_loss_func(cfg, args):
    """build loss function depends on train type

    Returns:
        torch loss function
    """
    mode = args.mode
    if mode == 'sl':
        pass
    elif mode == 'rl':
        pass

def build_optim(cfg, args, model):
    """train model by supervised learning

    Returns:
        torch optimizer
    """
    mode = args.mode
    if mode == 'sl':
        optim = cfg['train']['sl']['optim']
        lr = cfg['train']['sl']['learning_rate']
        if optim == 'SGD':
            return torch.optim.SGD(model.parameters(), lr=lr)        
        elif optim == 'ADAM':
            return torch.optim.Adam(model.parameters(), lr=lr)

    elif mode == 'rl':
        actor_optim = cfg['train']['rl']['optim']['actor']
        actor_lr = cfg['train']['rl']['learning_rate']['actor']
        critic_optim = cfg['train']['rl']['optim']['critic']
        critic_lr = cfg['train']['rl']['learning_rate']['critic']

        if actor_optim == 'SGD':
            actor_optim = torch.optim.SGD(model.actor.parameters(), lr=actor_lr)        
        elif actor_optim == 'ADAM':
            actor_optim = torch.optim.Adam(model.actor.parameters(), lr=actor_lr)

        if critic_optim == 'SGD':
            critic_optim = torch.optim.SGD(model.critic.parameters(), lr=critic_lr)        
        elif critic_optim == 'ADAM':
            critic_optim = torch.optim.Adam(model.critic.parameters(), lr=critic_lr)

        return actor_optim, critic_optim    
    
    # TODO : add optimizer


def build_scheduler(cfg, args, optim=None):
    """train model by supervised learning

    Returns:
        torch learning rate scheduler
    """
    mode = args.mode
    if mode == 'sl':
        scheduler_dict = cfg['train']['sl']['scheduler']
        return set_scheduler(optim[0], scheduler_dict)
    elif mode == 'rl':
        actor_scheduler_dict = cfg['train']['rl']['scheduler']['actor']
        critic_scheduler_dict = cfg['train']['rl']['scheduler']['critic']
        return set_scheduler(optim[0], actor_scheduler_dict), set_scheduler(optim[1], critic_scheduler_dict)

    def set_scheduler(optim, scheduler_dict):
        scheduler, spec = scheduler_dict.items()
        scheduler = scheduler.lower()
        
        if scheduler == 'multistep':
            return torch.optim.lr_scheduler.MultiStepLR(optim, milestones=[spec["milestones"]], gamma=spec["gamma"])
        elif scheduler == 'cyclic':
            return torch.optim.lr_scheduler.CyclicLR(optim, base_lr=spec["base_lr"], max_lr=spec["max_lr"])
    
    # TODO : add leraning rate scheduler

def plot_progress():
    """
    
    """
    pass

def log_progress():
    """

    """
    pass

def pfsp_function(beat_count, all_count, p=1, init_factor=50):
    """Calculate agent play priority value

    Args:
        beat_count: number of main agent beat specific agent
        all_count: number of plays between main agent and specific agent
        p: constant for how entropic the resulting distribution
        init_factor: constant for new agents to pull better

    Returns:
        agent priority value
    """
    beat_prob = beat_count / (all_count + init_factor)
    return (1 - beat_prob) ** p

def get_agent_ratio(play_history):
    """Calculate agent play probability
    
    Args:
        play_history: dictionary of number of wins and battles of the agents

    Returns:
        agent play probability
    """
    agent_ratio = {}
    sum_priority_value = 0
    for agent, info in play_history.items():
        # info[0] contains number of wins
        # info[1] contains number of battles
        priority_value = pfsp_function(info[0], info[1])
        agent_ratio[agent] = priority_value
        sum_priority_value += priority_value

    for agent, priority_value in agent_ratio.items():
        # info[0] contains number of wins
        # info[1] contains number of battles
        agent_ratio[agent] = priority_value/sum_priority_value

    return agent_ratio

def get_env_info(model, agents, play_history=None):
    """
    
    """
    # Batch data. For more details, check function header.
    batch_obs = []
    batch_acts = []
    batch_log_probs = []
    batch_rews = []
    batch_rtgs = []

    other_agent = agents[0] if agents[0] != None else agents[1]
    # Episodic data. Keeps track of rewards per episode, will get cleared
    # upon each new episode
    ep_rews = []

    t = 0 # Keeps track of how many timesteps we've run so far this batch

    while t < model.timesteps_per_batch:
        ep_rews = [] # rewards collected per episode

        # Reset the environment. sNote that obs is short for observation. 
        obs = model.env.reset(agents)
        done = False

        # Run an episode for a maximum of max_timesteps_per_episode timesteps
        for ep_t in range(model.max_timesteps_per_episode):
            t += 1 # Increment timesteps ran this batch so far

            # Track observations in this batch
            batch_obs.append(obs)

            # Calculate action and make a step in the env. 
            # Note that rew is short for reward.
            action, log_prob = model.get_action(obs)
            obs, rew, done, _ = model.env.step(action)

            # Track recent reward, action, and action log probability
            ep_rews.append(rew)
            batch_acts.append(action)
            batch_log_probs.append(log_prob)

            # If the environment tells us the episode is terminated, break
            if done:
                model.episode += 1
                if rew == 1:
                    play_history[other_agent][0] += 1
                play_history[other_agent][1] += 1
                break

        # Track episodic lengths and rewards
        batch_rews.append(ep_rews)

        # Reshape data as tensors in the shape specified in function description, before returning
        batch_obs = torch.tensor(batch_obs, dtype=torch.float)
        batch_acts = torch.tensor(batch_acts, dtype=torch.float)
        batch_log_probs = torch.tensor(batch_log_probs, dtype=torch.float)
        batch_rtgs = compute_rtgs(batch_rews)                                                              # ALG STEP 4

        return batch_obs, batch_acts, batch_log_probs, batch_rtgs, play_history

def compute_rtgs(model, batch_rews):
    """
        Compute the Reward-To-Go of each timestep in a batch given the rewards.
        Parameters:
            batch_rews - the rewards in a batch, Shape: (number of episodes, number of timesteps per episode)
        Return:
            batch_rtgs - the rewards to go, Shape: (number of timesteps in batch)
    """
    # The rewards-to-go (rtg) per episode per batch to return.
    # The shape will be (num timesteps per episode)
    batch_rtgs = []

    # Iterate through each episode
    for ep_rews in reversed(batch_rews):

        discounted_reward = 0 # The discounted reward so far

        # Iterate through all rewards in the episode. We go backwards for smoother calculation of each
        # discounted return (think about why it would be harder starting from the beginning)
        for rew in reversed(ep_rews):
            discounted_reward = rew + discounted_reward * model.gamma
            batch_rtgs.insert(0, discounted_reward)

    # Convert the rewards-to-go into a tensor
    batch_rtgs = torch.tensor(batch_rtgs, dtype=torch.float)

    return batch_rtgs