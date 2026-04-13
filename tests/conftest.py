"""
Shared fixtures for the Job Cannon test suite.
"""

import pytest
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent


SAMPLE_JOB_FRONTEND = {
    "title": "Frontend Developer",
    "company": "Shopify",
    "description": (
        "We're looking for a Frontend Developer to join our team. "
        "You'll be building beautiful, performant user interfaces with React.js and TypeScript. "
        "Requirements: 1+ years experience with React, familiarity with Next.js, "
        "understanding of responsive design and CSS-in-JS solutions, "
        "experience with REST APIs and GraphQL. "
        "Nice to have: experience with Tailwind CSS, testing with Jest/Cypress, "
        "CI/CD pipelines. We value clean code and attention to detail."
    ),
}

SAMPLE_JOB_BACKEND = {
    "title": "Backend Software Engineer",
    "company": "Wealthsimple",
    "description": (
        "Backend Software Engineer needed for our core platform team. "
        "You'll design and build scalable microservices handling millions of transactions. "
        "Requirements: Python or Node.js, PostgreSQL, Redis, REST API design, "
        "experience with Docker and Kubernetes, understanding of event-driven architecture. "
        "Fintech experience preferred. Strong understanding of database optimization "
        "and distributed systems. Experience with Django or Express.js is a plus."
    ),
}

SAMPLE_JOB_FULLSTACK = {
    "title": "Full Stack Developer",
    "company": "Stripe",
    "description": (
        "Full Stack Developer to work across our payments dashboard. "
        "You'll work on both the React frontend and Node.js backend services. "
        "Requirements: JavaScript/TypeScript, React.js, Node.js, PostgreSQL, "
        "experience with payment systems or financial APIs. "
        "You'll build features end-to-end from database schema to UI components. "
        "Experience with WebSocket, real-time systems, and agile development."
    ),
}


@pytest.fixture
def sample_jobs():
    """Three sample job descriptions covering frontend, backend, and fullstack."""
    return {
        "frontend": SAMPLE_JOB_FRONTEND,
        "backend": SAMPLE_JOB_BACKEND,
        "fullstack": SAMPLE_JOB_FULLSTACK,
    }


@pytest.fixture
def resume_config():
    """Standard resume config matching settings.yaml defaults."""
    return {
        "max_experiences": 4,
        "max_projects": 3,
        "max_bullets_per_exp": 3,
        "selection_strategy": "rule_based",
        "model": "claude-sonnet-4-20250514",
    }
