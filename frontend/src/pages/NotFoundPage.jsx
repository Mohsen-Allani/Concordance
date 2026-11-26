import { useNavigate } from 'react-router-dom';
import { Compass } from 'lucide-react';

import Button from '../components/ui/Button.jsx';
import { EmptyState } from '../components/ui/Feedback.jsx';

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="page">
      <EmptyState
        icon={Compass}
        title="Page introuvable"
        text="L'adresse demandée n'existe pas."
        action={
          <Button variant="primary" onClick={() => navigate('/app')}>
            Retour au tableau de bord
          </Button>
        }
      />
    </div>
  );
}
