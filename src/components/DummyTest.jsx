import React, { useState } from 'react';
import { motion } from 'framer-motion';

export default function DummyTest() {
  const [count, setCount] = useState(0);

  return (
    <div className="flex flex-col items-center justify-center p-8 m-4 bg-white rounded-xl shadow-lg border border-gray-100 max-w-md mx-auto">
      <h2 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-purple-600 mb-6">
        Frontend Test Area
      </h2>
      
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setCount(c => c + 1)}
        className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg shadow-sm hover:bg-blue-700 transition-all cursor-pointer"
      >
        Test Counter: {count}
      </motion.button>

      <div className="mt-6 p-4 bg-gray-50 rounded-lg text-gray-600 text-sm w-full text-center border border-gray-200">
        <p>This is a dummy component for UI testing.</p>
        <p className="mt-1 text-xs text-gray-400">Import me in App.jsx or main.jsx to see me!</p>
      </div>
    </div>
  );
}
