import { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  LayoutDashboard, 
  Database, 
  Layers, 
  Settings, 
  Activity,
  Moon,
  Sun,
  Wrench,
  GitBranch
} from 'lucide-react';
import { Button } from '../ui/button';
import { LanguageSwitcher } from '../LanguageSwitcher';
import { cn } from '@/lib/utils';

export function Layout() {
  const { t } = useTranslation();
  const [isDark, setIsDark] = useState(
    () => localStorage.getItem('theme') === 'dark'
  );

  const navigation = [
    { name: t('dashboard'), href: '/', icon: LayoutDashboard },
    { name: t('entities'), href: '/entities', icon: Database },
    { name: t('clusters'), href: '/clusters', icon: Layers },
    { name: 'Pipeline Debugger', href: '/pipeline-debugger', icon: GitBranch },
    { name: t('maintenance'), href: '/maintenance', icon: Wrench },
    { name: t('monitoring'), href: '/monitoring', icon: Activity },
    { name: t('settings'), href: '/settings', icon: Settings },
  ];

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  return (
    <div className="min-h-screen bg-background">
      {/* Home Assistant style header */}
      <header className="sticky top-0 z-50 border-b bg-primary text-primary-foreground shadow-sm">
        <div className="flex h-16 items-center px-6">
          <div className="flex items-center space-x-4">
            <div className="w-8 h-8 bg-primary-foreground rounded-md flex items-center justify-center">
              <span className="text-primary font-bold text-lg">🏠</span>
            </div>
            <h1 className="text-xl font-semibold text-primary-foreground">{t('appTitle')}</h1>
          </div>
          
          <nav className="flex items-center space-x-6 ml-8">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) =>
                  cn(
                    'flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-foreground/20 text-primary-foreground border border-primary-foreground/30'
                      : 'text-primary-foreground/70 hover:text-primary-foreground hover:bg-primary-foreground/10'
                  )
                }
              >
                <item.icon className="h-4 w-4" />
                <span>{item.name}</span>
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center space-x-4">
            <LanguageSwitcher />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsDark(!isDark)}
              className="text-primary-foreground hover:bg-primary-foreground/10"
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <div className="container mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}