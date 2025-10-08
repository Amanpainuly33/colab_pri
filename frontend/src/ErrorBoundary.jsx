import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    // Optionally log to a monitoring service
    // console.error('ErrorBoundary', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 16 }}>
          <h2>Something went wrong.</h2>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{String(this.state.error)}</pre>
          <button onClick={() => this.setState({ hasError: false, error: null })}>Retry</button>
        </div>
      )
    }
    return this.props.children
  }
}


