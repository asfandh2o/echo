import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'
import { Mail, Filter, MessageSquare, Calendar, Shield, Rocket, ArrowRight, ArrowLeft, Loader2 } from 'lucide-react'

const steps = [
  {
    icon: Mail,
    title: 'Welcome to ECHO',
    description: 'Your AI-powered email assistant. ECHO reads, understands, and drafts replies on your behalf — so you can focus on what matters.',
    detail: 'ECHO connects to your Gmail and works silently in the background, learning how you communicate over time.',
  },
  {
    icon: Filter,
    title: 'Smart Classification',
    description: 'Every incoming email is automatically categorized — work, personal, meetings, promotions, and more.',
    detail: 'Urgent emails are flagged and prioritized so nothing important slips through the cracks.',
  },
  {
    icon: MessageSquare,
    title: 'AI-Drafted Replies',
    description: 'ECHO drafts personalized replies based on the full conversation thread, your writing style, and who you\'re talking to.',
    detail: 'Every draft goes through a safety check to prevent hallucinated facts or risky commitments. The more you use ECHO, the better it gets.',
  },
  {
    icon: Calendar,
    title: 'Calendar Awareness',
    description: 'When someone proposes a meeting, ECHO checks your Google Calendar automatically.',
    detail: 'Free? It confirms the time and creates the event. Conflict? It suggests alternative available slots — all in the draft reply.',
  },
  {
    icon: Shield,
    title: 'You\'re in Control',
    description: 'Nothing is ever sent without your explicit approval. You always have the final say.',
    detail: 'Accept the AI draft as-is, edit it to your liking, or write your own reply. ECHO learns from every correction you make.',
  },
  {
    icon: Rocket,
    title: 'Let\'s Get Started',
    description: 'We\'ll fetch your latest emails and set everything up. This only takes a moment.',
    detail: 'ECHO will classify your emails, build contact profiles, and prepare draft suggestions — all automatically.',
  },
]

export default function Onboarding() {
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [fetchResult, setFetchResult] = useState(null)
  const navigate = useNavigate()
  const { completeOnboarding } = useAuth()

  const isLastStep = currentStep === steps.length - 1
  const step = steps[currentStep]
  const StepIcon = step.icon

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(prev => prev + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }

  const handleGetStarted = async () => {
    setLoading(true)
    try {
      const result = await api.fetchEmails(20)
      setFetchResult(result)

      await api.completeOnboarding()
      completeOnboarding()

      setTimeout(() => {
        navigate('/')
      }, 2000)
    } catch (err) {
      console.error('Onboarding fetch failed:', err)
      await api.completeOnboarding()
      completeOnboarding()
      navigate('/')
    }
  }

  return (
    <div className="app-container">
      <div className="onboarding-container">
        {/* Step indicator */}
        <div className="onboarding-dots">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`onboarding-dot ${i === currentStep ? 'active' : ''} ${i < currentStep ? 'completed' : ''}`}
            />
          ))}
        </div>

        {/* Step content */}
        <div className="onboarding-content">
          <div className="onboarding-icon">
            <StepIcon size={40} strokeWidth={1.5} />
          </div>

          <h1 className="onboarding-title">{step.title}</h1>
          <p className="onboarding-description">{step.description}</p>
          <p className="onboarding-detail">{step.detail}</p>
        </div>

        {/* Fetch result feedback on last step */}
        {isLastStep && loading && !fetchResult && (
          <div className="onboarding-loading">
            <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
            <span>Fetching your emails...</span>
          </div>
        )}

        {isLastStep && fetchResult && (
          <div className="onboarding-success">
            <span>Found {fetchResult.new} new email{fetchResult.new !== 1 ? 's' : ''}. Redirecting to your dashboard...</span>
          </div>
        )}

        {/* Navigation */}
        <div className="onboarding-actions">
          {currentStep > 0 && !loading && (
            <button className="btn btn-secondary" onClick={handleBack}>
              <ArrowLeft size={14} style={{ display: 'inline', marginRight: 6 }} />
              Back
            </button>
          )}

          {!isLastStep && (
            <button className="btn btn-primary" onClick={handleNext} style={{ marginLeft: 'auto' }}>
              Next
              <ArrowRight size={14} style={{ display: 'inline', marginLeft: 6 }} />
            </button>
          )}

          {isLastStep && !loading && !fetchResult && (
            <button className="btn btn-success" onClick={handleGetStarted} style={{ marginLeft: 'auto' }}>
              <Rocket size={14} style={{ display: 'inline', marginRight: 6 }} />
              Get Started
            </button>
          )}
        </div>

        {/* Skip option */}
        {!isLastStep && (
          <button
            className="onboarding-skip"
            onClick={() => setCurrentStep(steps.length - 1)}
          >
            Skip walkthrough
          </button>
        )}
      </div>
    </div>
  )
}
