import React from 'react';
import moment from 'moment';

export default function App() {
  return <div>{moment().format('LLL')}</div>;
}
