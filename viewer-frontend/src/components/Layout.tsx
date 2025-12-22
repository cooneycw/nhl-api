import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Activity, Download, Users, Calendar, CheckCircle, Shield, Menu, Fuel, HelpCircle, LayoutList, Stethoscope } from 'lucide-react'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'

const navigation = [
  { name: 'Dashboard', href: '/', icon: Activity },
  { name: 'Downloads', href: '/downloads', icon: Download },
  { name: 'Coverage', href: '/coverage', icon: Fuel },
  { name: 'Games', href: '/games', icon: Calendar },
  { name: 'Teams', href: '/teams', icon: Shield },
  { name: 'Players', href: '/players', icon: Users },
  { name: 'Lineups', href: '/lineups', icon: LayoutList },
  { name: 'Injuries', href: '/injuries', icon: Stethoscope },
  { name: 'Validation', href: '/validation', icon: CheckCircle },
  { name: 'Help', href: '/help', icon: HelpCircle },
]

export function Layout() {
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const NavLinks = ({ mobile = false }: { mobile?: boolean }) => (
    <>
      {navigation.map((item) => {
        const isActive = location.pathname === item.href
        return (
          <Link
            key={item.name}
            to={item.href}
            onClick={() => mobile && setMobileMenuOpen(false)}
            className={cn(
              'flex items-center space-x-2 transition-colors hover:text-foreground/80',
              mobile ? 'py-3 text-base' : 'text-sm',
              isActive ? 'text-foreground' : 'text-foreground/60'
            )}
          >
            <item.icon className={cn('h-4 w-4', mobile && 'h-5 w-5')} />
            <span>{item.name}</span>
          </Link>
        )
      })}
    </>
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <div className="mr-4 flex">
            <Link to="/" className="mr-6 flex items-center space-x-2">
              <Activity className="h-6 w-6" />
              <span className="font-bold">NHL Data Viewer</span>
            </Link>
          </div>

          {/* Desktop navigation */}
          <nav className="hidden md:flex items-center space-x-6 text-sm font-medium">
            <NavLinks />
          </nav>

          {/* Backend API link and theme toggle (desktop) */}
          <div className="hidden md:flex ml-auto items-center space-x-2">
            <a
              href="http://localhost:8000"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-foreground/60 hover:text-foreground/80 transition-colors"
            >
              API Docs ↗
            </a>
            <ThemeToggle />
          </div>

          {/* Mobile menu button */}
          <div className="ml-auto md:hidden">
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Toggle menu</span>
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-[280px]">
                <SheetHeader>
                  <SheetTitle className="flex items-center space-x-2">
                    <Activity className="h-5 w-5" />
                    <span>NHL Data Viewer</span>
                  </SheetTitle>
                </SheetHeader>
                <nav className="flex flex-col space-y-1 mt-6">
                  <NavLinks mobile />
                  <hr className="my-4" />
                  <a
                    href="http://localhost:8000"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center space-x-2 py-3 text-base text-foreground/60 hover:text-foreground/80 transition-colors"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span>API Docs ↗</span>
                  </a>
                  <div className="flex items-center justify-between py-3">
                    <span className="text-base text-foreground/60">Theme</span>
                    <ThemeToggle />
                  </div>
                </nav>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container py-6">
        <Outlet />
      </main>
    </div>
  )
}
