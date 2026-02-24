import React from 'react';
import { createRoot } from 'react-dom/client';
import { Page } from "./gui/pages/page";
import 'bootstrap/dist/js/bootstrap.bundle';
import 'bootstrap/dist/css/bootstrap.min.css';
import './index.css';

const root = createRoot(document.getElementById('root'));
root.render(<Page />);
