import { useState } from 'react';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import AuraBackground from './components/visuals/AuraBackground';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  return (
    <div className="antialiased text-text-primary selection:bg-primary/30 relative">
      <AuraBackground />
      {isAuthenticated ? (
        <Dashboard />
      ) : (
        <Auth onLogin={() => setIsAuthenticated(true)} />
      )}
    </div>
  );
}

export default App;
